"""
TCP BBRv3 congestion control.

This implementation follows the Linux BBRv3 design (netdev 0x16, 2023) and RFC 8899
guidance: it maintains separate STARTUP, DRAIN, PROBE_BW, and PROBE_RTT states,
tracks bandwidth with a windowed max filter, keeps a 10-second min-RTT sample, and
cycles pacing gains in PROBE_BW to gently probe for additional bandwidth.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List

from ns.flow.cc import CongestionControl


class BBRState(Enum):
    """BBRv3 states."""

    STARTUP = auto()
    DRAIN = auto()
    PROBE_BW = auto()
    PROBE_RTT = auto()


class ProbeBWPhase(Enum):
    """Sub-phases used while in PROBE_BW."""

    DOWN = auto()
    CRUISE = auto()
    REFILL = auto()
    UP = auto()


@dataclass
class _BandwidthSlot:
    value: float = 0.0
    timestamp: float = 0.0


class BBR(CongestionControl):
    """Implementation of the BBRv3 congestion controller."""

    # Bandwidth / RTT tracking parameters.
    BW_FILTER_LEN = 10
    FULL_BW_THRESHOLD = 1.25
    FULL_BW_REQUIRED_ROUNDS = 3
    PROBE_RTT_INTERVAL = 10.0  # seconds
    PROBE_RTT_DURATION = 0.2  # seconds

    # Gains (see Linux kernel implementation and BBRv3 paper).
    STARTUP_GAIN = 2.885
    CWND_GAIN = 2.0
    PROBE_DOWN_GAIN = 0.9
    PROBE_CRUISE_GAIN = 1.0
    PROBE_REFILL_GAIN = 1.0
    PROBE_UP_GAIN = 1.1

    LOSS_BETA = 0.8  # multiplicative decrease for inflight cap.

    def __init__(
        self,
        mss: int = 512,
        cwnd: int = 1 << 16,
        ssthresh: int = 65535,
        debug: bool = False,
        rtt_estimate: float = 0.1,
    ):
        super().__init__(mss, cwnd, ssthresh, debug)
        self.state = BBRState.STARTUP
        self.probe_phase = ProbeBWPhase.DOWN
        self.pacing_gain = self.STARTUP_GAIN
        self.cwnd_gain = self.CWND_GAIN
        self.initial_rtt = max(rtt_estimate, 1e-3)
        self.BBRMinPipeCwnd = 4 * self.mss

        # Filters / timers.
        self.max_bw_slots: List[_BandwidthSlot] = [
            _BandwidthSlot() for _ in range(self.BW_FILTER_LEN)
        ]
        self.max_bw_index = 0
        self.max_bw = 0.0
        self.min_rtt = float("inf")
        self.min_rtt_stamp = 0.0
        self.probe_rtt_start = None
        self.next_probe_rtt = self.PROBE_RTT_INTERVAL

        # Round tracking.
        self.round_start = False
        self.next_round_delivered = 0
        self.full_bw = 0.0
        self.full_bw_rounds = 0
        self.filled_pipe = False

        # Probe BW cycle.
        self.probe_cycle: List[ProbeBWPhase] = [
            ProbeBWPhase.DOWN,
            ProbeBWPhase.CRUISE,
            ProbeBWPhase.REFILL,
            ProbeBWPhase.UP,
        ]
        self.probe_cycle_index = 0
        self.cycle_start_time = 0.0

        self.packet_in_flight = 0.0
        self.current_time = 0.0
        self.packet_conservation = False
        self.loss_in_round = False

        # Initialize pacing rate aggressively (startup gain * initial cwnd / RTT).
        self.pacing_rate = (self.cwnd / self.initial_rtt) * self.STARTUP_GAIN

    # ------------------------------------------------------------------ #
    # Public API expected by the packet generator
    # ------------------------------------------------------------------ #

    def set_before_control(self, current_time, packet_in_flight: int = 0):
        self.current_time = current_time
        self.packet_in_flight = packet_in_flight

    def ack_received(self, rtt: float = 0.0, current_time: float = 0.0):
        """Called for every cumulative ACK with its RTT sample."""
        if self.rs is None or self.C is None:
            return
        self.current_time = current_time
        if rtt > 0:
            self.rs.rtt = rtt
        self._update_round()
        self._update_bandwidth()
        self._update_min_rtt(rtt)
        self._check_full_pipe()
        self._maybe_enter_or_exit_probe_rtt()
        self._maybe_update_probe_bw_phase()
        self._update_gains()
        self._update_pacing_rate()
        self._update_cwnd()

    def timer_expired(self, packet=None):
        """Packets timed out – fall back to packet conservation."""
        del packet
        self.packet_conservation = True
        self.cwnd = max(self.BBRMinPipeCwnd, self.packet_in_flight + self.mss)

    def consecutive_dupacks_received(self, packet=None):
        del packet
        self.packet_conservation = True

    def more_dupacks_received(self, packet=None):
        del packet
        self.packet_conservation = True

    def dupack_over(self):
        self.packet_conservation = False

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _update_round(self):
        delivered = self.C.delivered
        if self.rs.prior_delivered >= self.next_round_delivered:
            self.next_round_delivered = delivered
            self.round_start = True
        else:
            self.round_start = False

    def _update_bandwidth(self):
        rate = self.rs.delivery_rate
        if rate <= 0:
            return
        should_replace = (
            not self.rs.is_app_limited or rate >= self.max_bw * 0.98
        )
        if should_replace:
            self.max_bw_slots[self.max_bw_index] = _BandwidthSlot(rate, self.current_time)
            self.max_bw_index = (self.max_bw_index + 1) % self.BW_FILTER_LEN
            self.max_bw = max(slot.value for slot in self.max_bw_slots)

    def _update_min_rtt(self, sample_rtt: float):
        if sample_rtt > 0 and sample_rtt < self.min_rtt:
            self.min_rtt = sample_rtt
            self.min_rtt_stamp = self.current_time

    def _check_full_pipe(self):
        if self.state != BBRState.STARTUP:
            return
        rate = self.rs.delivery_rate
        if rate <= 0:
            return
        if rate >= self.full_bw * self.FULL_BW_THRESHOLD:
            self.full_bw = rate
            self.full_bw_rounds = 0
        else:
            self.full_bw_rounds += 1
            if self.full_bw_rounds >= self.FULL_BW_REQUIRED_ROUNDS:
                self.filled_pipe = True

    def _maybe_enter_or_exit_probe_rtt(self):
        if self.state == BBRState.PROBE_RTT:
            if (
                self.probe_rtt_start is not None
                and self.current_time - self.probe_rtt_start >= self.PROBE_RTT_DURATION
                and self.packet_in_flight <= self.BBRMinPipeCwnd
            ):
                self._exit_probe_rtt()
            return

        # Enter PROBE_RTT if the min-RTT sample is stale.
        if self.current_time - self.min_rtt_stamp >= self.PROBE_RTT_INTERVAL:
            self._enter_probe_rtt()

    def _enter_probe_rtt(self):
        self.state = BBRState.PROBE_RTT
        self.probe_rtt_start = self.current_time
        self.next_probe_rtt = self.current_time + self.PROBE_RTT_INTERVAL
        self.pacing_gain = 1.0
        self.cwnd_gain = 1.0

    def _exit_probe_rtt(self):
        self.state = BBRState.PROBE_BW if self.filled_pipe else BBRState.STARTUP
        self.probe_rtt_start = None
        self._reset_probe_bw_cycle()

    def _maybe_update_probe_bw_phase(self):
        if self.state not in (BBRState.DRAIN, BBRState.STARTUP):
            if self.state == BBRState.PROBE_BW and self.round_start:
                self.probe_cycle_index = (self.probe_cycle_index + 1) % len(
                    self.probe_cycle
                )
                self.probe_phase = self.probe_cycle[self.probe_cycle_index]
                self.cycle_start_time = self.current_time
        # Handle STARTUP/DRAIN transitions.
        if self.state == BBRState.STARTUP and self.filled_pipe:
            self.state = BBRState.DRAIN
        if self.state == BBRState.DRAIN and self.packet_in_flight <= self._target_inflight(
            1.0
        ):
            self.state = BBRState.PROBE_BW
            self._reset_probe_bw_cycle()

    def _reset_probe_bw_cycle(self):
        self.probe_cycle_index = 0
        self.probe_phase = self.probe_cycle[0]
        self.cycle_start_time = self.current_time

    def _update_gains(self):
        if self.state == BBRState.STARTUP:
            self.pacing_gain = self.STARTUP_GAIN
            self.cwnd_gain = self.CWND_GAIN
        elif self.state == BBRState.DRAIN:
            self.pacing_gain = 1.0 / self.STARTUP_GAIN
            self.cwnd_gain = self.CWND_GAIN
        elif self.state == BBRState.PROBE_BW:
            if self.probe_phase == ProbeBWPhase.DOWN:
                self.pacing_gain = self.PROBE_DOWN_GAIN
            elif self.probe_phase == ProbeBWPhase.CRUISE:
                self.pacing_gain = self.PROBE_CRUISE_GAIN
            elif self.probe_phase == ProbeBWPhase.REFILL:
                self.pacing_gain = self.PROBE_REFILL_GAIN
            else:
                self.pacing_gain = self.PROBE_UP_GAIN
            self.cwnd_gain = self.CWND_GAIN
        else:  # PROBE_RTT
            self.pacing_gain = 1.0
            self.cwnd_gain = 1.0

    def _update_pacing_rate(self):
        bw = self.max_bw
        if bw <= 0:
            # Fall back to initial estimates.
            bw = self.cwnd / self.initial_rtt
        self.pacing_rate = max(
            (self.mss / max(self.min_rtt if self.min_rtt < float("inf") else self.initial_rtt, 1e-6)),
            self.pacing_gain * bw,
        )

    def _target_inflight(self, gain: float) -> float:
        bw = self.max_bw
        rtt = self.min_rtt if self.min_rtt < float("inf") else self.initial_rtt
        if bw <= 0 or rtt <= 0:
            return self.cwnd
        return gain * bw * rtt

    def _update_cwnd(self):
        newly_lost = getattr(self.rs, "newly_lost", 0) or 0
        if newly_lost > 0:
            self.packet_conservation = True
            self.cwnd = max(self.BBRMinPipeCwnd, self.packet_in_flight * self.LOSS_BETA)

        target = self._target_inflight(self.cwnd_gain)
        if self.state == BBRState.PROBE_RTT:
            target = min(target, self.BBRMinPipeCwnd)
        if self.packet_conservation:
            target = max(target, self.packet_in_flight + getattr(self.rs, "newly_acked", 0))

        if self.cwnd < target:
            self.cwnd += getattr(self.rs, "newly_acked", 0)
        self.cwnd = max(self.BBRMinPipeCwnd, min(self.cwnd, target))

        # Exit packet conservation once inflight matches cwnd.
        if self.packet_conservation and self.packet_in_flight <= self.cwnd:
            self.packet_conservation = False
