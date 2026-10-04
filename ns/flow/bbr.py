"""Educational BBR: a delivery-rate/propagation-delay model with paced probes.

This small controller implements the core BBR model, not Linux BBRv3. Its
round-based bandwidth filter and Startup/Drain/ProbeRTT follow BBRv1; the four
named ProbeBW phases are a deterministic teaching cycle. See docs/bbr.md for
references, precise behavior, and omitted production mechanisms.
"""

import math
from enum import Enum, auto

from ns.flow.cc import CongestionControl
from ns.packet.rate_sample import Connection, RateSample


class BBRState(Enum):
    """The four core BBR operating modes."""

    STARTUP = auto()
    DRAIN = auto()
    PROBE_BW = auto()
    PROBE_RTT = auto()


class ProbeBWPhase(Enum):
    """A simplified drain/cruise/refill/probe cycle, not the v3 state machine."""

    DOWN = auto()
    CRUISE = auto()
    REFILL = auto()
    UP = auto()


class BBR(CongestionControl):
    """Estimate BDP in bytes; pace in bytes/second; all clocks are seconds."""

    BW_FILTER_LEN = 10  # Packet-timed rounds, not ACKs or wall-clock seconds.
    FULL_BW_THRESHOLD = 1.25
    FULL_BW_REQUIRED_ROUNDS = 3
    PROBE_RTT_INTERVAL = 10.0
    PROBE_RTT_DURATION = 0.2
    STARTUP_GAIN = 2.885
    CWND_GAIN = 2.0
    PROBE_DOWN_GAIN = 0.9
    PROBE_CRUISE_GAIN = 1.0
    PROBE_REFILL_GAIN = 1.0
    PROBE_UP_GAIN = 1.1

    def __init__(
        self, mss: int = 512, cwnd: int = 1 << 16, ssthresh: int = 65535,
        debug: bool = False, rtt_estimate: float = 0.1,
    ) -> None:
        super().__init__(mss, cwnd, ssthresh, debug)
        if not math.isfinite(rtt_estimate) or rtt_estimate <= 0:
            raise ValueError("rtt_estimate must be finite and positive")
        self.state = BBRState.STARTUP
        self.pacing_gain = self.STARTUP_GAIN
        self.cwnd_gain = self.CWND_GAIN
        self.initial_rtt = rtt_estimate
        self.initial_cwnd = cwnd
        self.BBRMinPipeCwnd = 4 * self.mss
        self.max_bw = 0.0
        # One maximum per packet-timed round keeps ACK density out of the filter.
        self._bandwidth_rounds: dict[int, float] = {}
        self.min_rtt = float("inf")
        self.min_rtt_stamp: float | None = None
        self.probe_rtt_start: float | None = None
        self._probe_rtt_round_done = False
        self._prior_cwnd = cwnd
        self.round_count = 0
        self.round_start = False
        self.next_round_delivered = 0
        self.full_bw = 0.0
        self.full_bw_rounds = 0
        self.filled_pipe = False
        self.probe_cycle = list(ProbeBWPhase)
        self.probe_cycle_index = 0
        self.probe_phase = ProbeBWPhase.DOWN
        self.cycle_start_time = 0.0
        self.packet_in_flight = 0
        self.current_time = 0.0
        self.packet_conservation = False
        self._recovery_delivered = 0
        self._recovery_cwnd = cwnd
        self.pacing_rate = self.STARTUP_GAIN * cwnd / rtt_estimate

    def set_before_control(
        self, current_time: float, packet_in_flight: float = 0
    ) -> None:
        """The sender reports actual remaining unique bytes after an ACK."""
        self.current_time = current_time
        self.packet_in_flight = packet_in_flight

    @property
    def _sample(self) -> RateSample:
        """The sender attaches rate feedback before invoking BBR transitions."""
        assert self.rs is not None
        return self.rs

    @property
    def _connection(self) -> Connection:
        assert self.C is not None
        return self.C

    def ack_received(
        self, rtt: float | None = None, current_time: float = 0.0
    ) -> None:
        """Apply one advancing ACK's rate, RTT and exact newly-ACKed byte count."""
        if self.rs is None or self.C is None:
            return
        self.current_time = current_time
        self._update_round()
        self._update_bandwidth()
        # Determine expiry before replacing an expired minimum with a new RTT.
        expired = (self.min_rtt_stamp is not None
                   and current_time - self.min_rtt_stamp >= self.PROBE_RTT_INTERVAL)
        if self._sample.rtt >= 0 and rtt is not None and rtt >= 0 and math.isfinite(rtt):
            if rtt < self.min_rtt or expired:
                self.min_rtt = rtt
                self.min_rtt_stamp = current_time
        self._check_full_pipe()
        self._update_probe_rtt(expired)
        self._update_probe_bw()
        self._update_gains()
        # Startup never lowers pacing before finding the full pipe. An early
        # ACK may understate capacity; later modes can follow decreasing rates.
        rate = self.pacing_gain * (self.max_bw or self.initial_cwnd / self.initial_rtt)
        if self.state != BBRState.STARTUP or rate > self.pacing_rate:
            self.pacing_rate = rate
        self._update_cwnd()

    def _enter_recovery(self) -> None:
        if not self.packet_conservation:
            # A ProbeRTT cap is temporary: retain its saved window on loss.
            self._recovery_cwnd = (max(self.cwnd, self._prior_cwnd)
                                   if self.state == BBRState.PROBE_RTT
                                   else self.cwnd)
        self.packet_conservation = True
        self._recovery_delivered = self._connection.delivered + self.packet_in_flight
        # Retransmitting creates no new byte credit. Subsequent ACKs release
        # their acknowledged bytes; the four-segment minimum keeps the pipe live.
        self.cwnd = max(self.BBRMinPipeCwnd, self.packet_in_flight)

    def timer_expired(self, packet: object | None = None) -> None:
        """Conserve the flight that existed at timeout, until it is delivered."""
        self._enter_recovery()

    def consecutive_dupacks_received(self, packet: object | None = None) -> None:
        """Fast retransmit begins the same byte conservation as timeout."""
        self._enter_recovery()

    def more_dupacks_received(self, packet: object | None = None) -> None:
        """Duplicate ACKs do not acknowledge bytes or grow the BBR window."""

    def dupack_over(self) -> None:
        """The transport's recovery frontier is covered; restore saved credit."""
        if self.packet_conservation:
            self.cwnd = max(self.cwnd, self._recovery_cwnd)
        self.packet_conservation = False

    def _update_round(self) -> None:
        # Invalid rate intervals can still carry delivery-frontier observations.
        self.round_start = (self._sample.newly_acked > 0
                            and self._sample.prior_time is not None
                            and self._sample.prior_delivered >= self.next_round_delivered)
        if self.round_start:
            self.round_count += 1
            self.next_round_delivered = self._connection.delivered

    def _valid_rate(self) -> bool:
        return (self._sample.interval > 0 and math.isfinite(self._sample.interval)
                and self._sample.delivery_rate > 0
                and math.isfinite(self._sample.delivery_rate))

    def _update_bandwidth(self) -> None:
        if not self._valid_rate():
            return
        rate = self._sample.delivery_rate
        # An application-limited sample may discover a higher bandwidth, but it
        # cannot replace or age out an estimate the application did not exercise.
        if self._sample.is_app_limited and rate < self.max_bw:
            return
        self._bandwidth_rounds = {
            round_id: value for round_id, value in self._bandwidth_rounds.items()
            if round_id > self.round_count - self.BW_FILTER_LEN
        }
        self._bandwidth_rounds[self.round_count] = max(
            rate, self._bandwidth_rounds.get(self.round_count, 0),
        )
        self.max_bw = max(self._bandwidth_rounds.values())

    def _check_full_pipe(self) -> None:
        if (self.state != BBRState.STARTUP or not self.round_start
                or self._sample.is_app_limited or not self._valid_rate()):
            return
        if self.max_bw >= self.full_bw * self.FULL_BW_THRESHOLD:
            self.full_bw = self.max_bw
            self.full_bw_rounds = 0
        else:
            self.full_bw_rounds += 1
            if self.full_bw_rounds >= self.FULL_BW_REQUIRED_ROUNDS:
                self.filled_pipe = True

    def _update_probe_rtt(self, expired: bool) -> None:
        if self.state != BBRState.PROBE_RTT and expired:
            # Recovery also caps temporarily; neither mode may erase the
            # other's saved credit while their drain/hold periods overlap.
            self._prior_cwnd = (max(self.cwnd, self._recovery_cwnd)
                                if self.packet_conservation else self.cwnd)
            self.state = BBRState.PROBE_RTT
            self.probe_rtt_start = None
            self._probe_rtt_round_done = False
        if self.state != BBRState.PROBE_RTT:
            return
        # Probe samples are application-limited because we intentionally reduce
        # flight. Their low delivery rate must not erase the bandwidth estimate.
        self._connection.mark_connection_app_limited(self.packet_in_flight)
        if self.probe_rtt_start is None:
            if self.packet_in_flight <= self.BBRMinPipeCwnd:
                self.probe_rtt_start = self.current_time
                self.next_round_delivered = self._connection.delivered
        else:
            self._probe_rtt_round_done |= self.round_start
            held = self.current_time - self.probe_rtt_start
            if (self._probe_rtt_round_done
                    and self.packet_in_flight <= self.BBRMinPipeCwnd
                    and held >= self.PROBE_RTT_DURATION):
                self.min_rtt_stamp = self.current_time
                self.cwnd = max(self.cwnd, self._prior_cwnd)
                self.state = BBRState.PROBE_BW if self.filled_pipe else BBRState.STARTUP
                self.probe_rtt_start = None
                self._reset_probe_bw_cycle()

    def _update_probe_bw(self) -> None:
        if self.state == BBRState.STARTUP and self.filled_pipe:
            self.state = BBRState.DRAIN
        if self.state == BBRState.DRAIN:
            if self.packet_in_flight <= self._target_inflight(1):
                self.state = BBRState.PROBE_BW
                self._reset_probe_bw_cycle()
        elif (self.state == BBRState.PROBE_BW
              and (self.round_start or (self.probe_phase == ProbeBWPhase.UP
                                        and self._sample.newly_lost > 0))):
            # DOWN waits for actual drain; UP waits a propagation RTT and ends
            # early on loss. CRUISE and REFILL each last one packet-timed round.
            drained = self.packet_in_flight <= self._target_inflight(1)
            elapsed = self.current_time - self.cycle_start_time
            if ((self.probe_phase != ProbeBWPhase.DOWN or drained)
                    and (self.probe_phase != ProbeBWPhase.UP
                         or elapsed >= self._model_rtt() or self._sample.newly_lost > 0)):
                self.probe_cycle_index = (
                    (self.probe_cycle_index + 1) % len(self.probe_cycle)
                )
                self.probe_phase = self.probe_cycle[self.probe_cycle_index]
                self.cycle_start_time = self.current_time

    def _reset_probe_bw_cycle(self) -> None:
        self.probe_cycle_index = 0
        self.probe_phase = self.probe_cycle[0]
        self.cycle_start_time = self.current_time

    def _update_gains(self) -> None:
        self.cwnd_gain = self.CWND_GAIN
        if self.state == BBRState.STARTUP:
            self.pacing_gain = self.STARTUP_GAIN
        elif self.state == BBRState.DRAIN:
            self.pacing_gain = 1 / self.STARTUP_GAIN
        elif self.state == BBRState.PROBE_BW:
            gains = (self.PROBE_DOWN_GAIN, self.PROBE_CRUISE_GAIN,
                     self.PROBE_REFILL_GAIN, self.PROBE_UP_GAIN)
            self.pacing_gain = gains[self.probe_cycle_index]
        else:
            self.pacing_gain = self.cwnd_gain = 1

    def _model_rtt(self) -> float:
        return self.min_rtt if math.isfinite(self.min_rtt) else self.initial_rtt

    def _target_inflight(self, gain: float) -> float:
        # bytes/second * seconds = bytes; no link-rate bit conversion here.
        if self.max_bw:
            return gain * self.max_bw * self._model_rtt()
        return self.initial_cwnd

    def _update_cwnd(self) -> None:
        acked = self._sample.newly_acked
        if self.packet_conservation and self._connection.delivered >= self._recovery_delivered:
            self.dupack_over()
        if self.packet_conservation:
            self.cwnd = max(self.BBRMinPipeCwnd, self.packet_in_flight + acked)
        else:
            target = max(self.BBRMinPipeCwnd, self._target_inflight(self.cwnd_gain))
            # Startup grows with delivered bytes; only a filled pipe uses the
            # BDP cap. Otherwise an early low sample can suppress startup growth.
            self.cwnd += acked
            if self.filled_pipe:
                self.cwnd = min(self.cwnd, target)
            self.cwnd = max(self.BBRMinPipeCwnd, self.cwnd)
        if self.state == BBRState.PROBE_RTT:
            self.cwnd = min(self.cwnd, self.BBRMinPipeCwnd)
