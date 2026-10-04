"""A byte-sequenced TCP sender with cumulative ACKs and loss recovery.

Congestion control chooses a byte window; this transport owns segmentation,
logical outstanding data, RTT sampling, and one retransmission timer. It models
neither TCP timestamps nor SACK, so ambiguous ACKs cannot supply RTT samples.
"""

from dataclasses import dataclass
import math

import simpy

from ns.packet.packet import Packet
from ns.utils.timer import Timer


@dataclass
class SegmentState:
    """An unacknowledged byte range, independent of any physical send attempt."""

    seq: int
    size: int
    first_tx_time: float
    last_tx_time: float
    retransmit_count: int = 0
    # A partial ACK makes timing ambiguous even if the suffix was never resent.
    rtt_eligible: bool = True


class TCPPacketGenerator:
    """Generate TCP data from a Flow and a congestion-control byte window.

    ``start_time`` and ``finish_time`` are absolute simulation seconds. The
    finish boundary excludes new data, while already transmitted data continues
    to be acknowledged or retransmitted. An omitted finish time is unbounded.
    The maximum data segment size follows ``cc.mss`` (512 for older controllers
    without that attribute). Public sequence/window fields are measured in bytes.
    """

    def __init__(self, env, flow, cc, element_id=None, debug=False):
        self.env = env
        self.flow = flow
        self.congestion_control = cc
        self.element_id = element_id
        self.debug = debug
        self.out = None
        self.mss = getattr(cc, "mss", 512)
        if isinstance(self.mss, bool) or not isinstance(self.mss, int) or self.mss <= 0:
            raise ValueError("TCP MSS must be a positive integer byte count.")
        if flow.size is not None and (
            isinstance(flow.size, bool) or not isinstance(flow.size, int)
            or flow.size < 0
        ):
            raise ValueError("TCP flow size must be a nonnegative integer byte count.")

        self.last_arrival = env.now
        self.next_seq = 0       # SND.NXT: next new byte to transmit
        self.send_buffer = 0    # application byte frontier (sent or waiting)
        self.last_ack = 0       # SND.UNA: oldest unacknowledged byte
        self.dupack = 0
        self.recovery_high_sequence = None
        self.rtt_var = 0.0
        self.smoothed_rtt = 0.0
        self.rto = 1.0
        self.last_rtt_sample = 0.0
        # Zero-delay compositions can measure RTT=0; zero is not a sentinel.
        self._rtt_initialized = False
        self.cwnd_available = simpy.Store(env)

        self.segment_state = {}
        # Retain the latest physical attempt for inspection; logical state above
        # is authoritative and is never reconstructed from mutable packets.
        self.sent_packets = {}
        self.timer = None
        # Compatibility view: at most one entry, keyed by the oldest byte range.
        self.timers = {}
        self.action = env.process(self.run())

    @property
    def bytes_in_flight(self):
        """Unique sent bytes not yet covered by the cumulative ACK."""
        return self.next_seq - self.last_ack

    def _build_packet(self, state):
        """Emit fresh attempt metadata, retaining the original latency clock."""
        return Packet(
            state.first_tx_time,
            state.size,
            state.seq,
            src=self.flow.src,
            dst=self.flow.dst,
            flow_id=self.flow.fid,
        )

    def _restart_timer(self):
        """Arm one deadline from now for the oldest outstanding byte range."""
        self.timers.clear()
        if not self.segment_state:
            if self.timer is not None:
                self.timer.stop()
            return

        oldest = min(self.segment_state)
        if self.timer is None:
            self.timer = Timer(self.env, oldest, self.timeout_callback, self.rto)
        else:
            self.timer.timer_id = oldest
            self.timer.restart(self.rto)
        self.timers[oldest] = self.timer

    def _send_new_packet(self, packet_size):
        """Register the whole send transition before synchronous downstream put."""
        state = SegmentState(self.next_seq, packet_size, self.env.now, self.env.now)
        packet = self._build_packet(state)
        self.segment_state[state.seq] = state
        self.sent_packets[state.seq] = packet
        self.next_seq += packet_size
        # Later new segments share the oldest segment's deadline (RFC 6298 §5).
        if not self.timers:
            self._restart_timer()
        if self.debug:
            print(
                f"TCP {self.element_id} sends seq={state.seq}, "
                f"bytes={state.size} at {self.env.now:.4f}."
            )
        self.out.put(packet)
        return packet

    def _retransmit(self, state):
        """Record an attempt before forwarding, even if forwarding ACKs inline."""
        state.retransmit_count += 1
        state.last_tx_time = self.env.now
        packet = self._build_packet(state)
        self.sent_packets[state.seq] = packet
        if self.debug:
            print(
                f"TCP {self.element_id} retransmits seq={state.seq}, "
                f"bytes={state.size} at {self.env.now:.4f}."
            )
        self.out.put(packet)

    def _retransmit_after_ack(self, state, sequence, retransmit_count):
        """Yield one turn so synchronous partial ACKs cannot recurse unboundedly."""
        yield self.env.timeout(0)
        # Feedback may retire/trim the range, or another attempt may supersede
        # this recovery request before its turn. Only a still-missing hole sends.
        if (
            self.segment_state.get(sequence) is state
            and self.last_ack == sequence
            and self.recovery_high_sequence is not None
            and state.retransmit_count == retransmit_count
        ):
            self._retransmit(state)

    def _wake_sender(self):
        """Coalesce window notifications; the run loop rechecks byte credit."""
        if not self.cwnd_available.items:
            self.cwnd_available.put(True)

    def _before_control(self):
        """Supply pre-feedback flight size to controllers that accept context."""
        hook = getattr(self.congestion_control, "set_before_control", None)
        if hook is not None:
            hook(self.env.now, self.bytes_in_flight)

    def run(self):
        """Wait for application data or ACK credit, bounded by new-data finish."""
        start = self.flow.start_time
        finish = self.flow.finish_time
        if start is not None and start > self.env.now:
            # A start beyond finish cannot create new application data.
            wake = start if finish is None else min(start, finish)
            yield self.env.timeout(max(0, wake - self.env.now))
        self.last_arrival = self.env.now

        while finish is None or self.env.now < finish:
            if self.flow.size is not None and self.next_seq >= self.flow.size:
                return

            if self.next_seq >= self.send_buffer:
                if self.flow.arrival_dist is not None:
                    interval = self.flow.arrival_dist()
                    if not math.isfinite(interval) or interval < 0:
                        raise ValueError("TCP application intervals must be nonnegative.")
                    # Preserve the application's arrival clock while blocked on
                    # a window; past arrivals can be consumed without extra delay.
                    arrival = self.last_arrival + interval
                    if finish is not None and arrival >= finish:
                        yield self.env.timeout(finish - self.env.now)
                        return
                    yield self.env.timeout(max(0, arrival - self.env.now))
                    self.last_arrival = arrival
                    if finish is not None and self.env.now >= finish:
                        return

                amount = (
                    self.mss if self.flow.size_dist is None
                    else self.flow.size_dist()
                )
                if not math.isfinite(amount) or amount < 1:
                    # Zero-byte, zero-time application bursts would otherwise
                    # make a non-yielding loop. Sources supply at least one byte.
                    raise ValueError("TCP application bursts must contain a byte.")
                # Application distributions may be continuous; TCP transmits
                # whole bytes, rounding each burst down rather than inventing data.
                amount = int(amount)
                if self.flow.size is not None:
                    amount = min(amount, self.flow.size - self.send_buffer)
                self.send_buffer += amount

            # All quantities here are bytes. Fractional controller credit is
            # retained in cwnd but cannot become a fractional sequence or packet.
            credit = max(
                0, math.floor(self.congestion_control.cwnd) - self.bytes_in_flight
            )
            amount = min(self.mss, self.send_buffer - self.next_seq, credit)
            if amount > 0:
                self._send_new_packet(amount)
            else:
                notification = self.cwnd_available.get()
                if finish is None:
                    yield notification
                else:
                    yield notification | self.env.timeout(finish - self.env.now)
                    # Remove a parked Store.get if the deadline won the race.
                    if not notification.triggered:
                        notification.cancel()

    def timeout_callback(self, packet_id=0):
        """Retransmit only the oldest outstanding range and double the RTO."""
        if not self.segment_state or packet_id not in self.timers:
            return
        state = self.segment_state[packet_id]
        self._before_control()
        self.congestion_control.timer_expired()
        self.dupack = 0
        self.recovery_high_sequence = None
        # Backoff belongs to the connection, including its next new-data timer.
        # Match Days's 60-second maximum (permitted by RFC 6298 §2.5).
        self.rto = min(60.0, self.rto * 2)
        self._restart_timer()
        self._retransmit(state)

    def _update_rtt(self, sample):
        """RFC 6298 estimator: update variance using the previous SRTT."""
        if not self._rtt_initialized:
            self.smoothed_rtt = sample
            self.rtt_var = sample / 2
            self._rtt_initialized = True
        else:
            self.rtt_var = 0.75 * self.rtt_var + 0.25 * abs(
                self.smoothed_rtt - sample
            )
            self.smoothed_rtt = 0.875 * self.smoothed_rtt + 0.125 * sample
        # Days uses a 1 ms estimator granularity. This lower bound on variation
        # does not quantize the simulator clock or floating-point RTT samples.
        self.rto = min(
            60.0, max(1.0, self.smoothed_rtt + max(0.001, 4 * self.rtt_var))
        )
        self.last_rtt_sample = sample

    def put(self, ack):
        """Accept only this flow's cumulative ACKs within transmitted bytes."""
        sequence = ack.ack
        if (
            ack.flow_id != self.flow.fid + 10000
            or not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or sequence < self.last_ack
            or sequence > self.next_seq
            or not self.segment_state
        ):
            return

        if sequence == self.last_ack:
            self.dupack += 1
            if self.recovery_high_sequence is None and self.dupack == 3:
                # Recovery covers the bytes outstanding at entry. Later duplicate
                # ACKs may send fresh bytes but never move this exit frontier.
                self.recovery_high_sequence = self.next_seq
                self._before_control()
                self.congestion_control.consecutive_dupacks_received()
                self._restart_timer()
                self._retransmit(self.segment_state[sequence])
            elif self.recovery_high_sequence is not None:
                self._before_control()
                self.congestion_control.more_dupacks_received()
                self._wake_sender()
            return

        previous_ack = self.last_ack
        first = self.segment_state[previous_ack]
        # Without timestamps, only an ACK for exactly one complete, never-resent
        # segment has an unambiguous sample. Do not trust echoed packet.time.
        sample = None
        if (
            sequence == previous_ack + first.size
            and first.retransmit_count == 0
            and first.rtt_eligible
        ):
            sample = self.env.now - first.first_tx_time
            self._update_rtt(sample)
        self._before_control()
        self.last_ack = sequence
        self.dupack = 0

        # Retire complete ranges; trim a partially ACKed range to its outstanding
        # suffix. Physical attempts already downstream remain untouched.
        for seq, state in list(self.segment_state.items()):
            end = seq + state.size
            if end <= sequence:
                del self.segment_state[seq]
                del self.sent_packets[seq]
            elif seq < sequence:
                del self.segment_state[seq]
                attempt = self.sent_packets.pop(seq)
                state.seq = sequence
                state.size = end - sequence
                state.rtt_eligible = False
                self.segment_state[sequence] = state
                # The last physical attempt may also contain ACKed prefix bytes;
                # retain it for inspection without mutating downstream ownership.
                self.sent_packets[sequence] = attempt

        self._restart_timer()
        if self.recovery_high_sequence is not None:
            if sequence < self.recovery_high_sequence:
                # A NewReno partial ACK signals another hole: stay in recovery
                # and retransmit it without repeating the fast-loss reduction.
                hook = getattr(self.congestion_control, "partial_ack_received", None)
                if hook is not None:
                    hook(sequence - previous_ack, self.env.now)
                state = self.segment_state[sequence]
                # Keep ACK processing synchronous, but let its forwarding stack
                # unwind before the next hole can synchronously produce an ACK.
                self.env.process(
                    self._retransmit_after_ack(state, sequence, state.retransmit_count)
                )
            else:
                self.recovery_high_sequence = None
                self.congestion_control.dupack_over()
                # The exit ACK does not also grow the congestion window.
        else:
            rtt = self.smoothed_rtt if sample is None else sample
            # Built-in loss controllers need the exact frontier advance, even
            # for short or cumulative ACKs. The bridge carries only a fresh
            # Karn sample (None if ambiguous); old custom callbacks keep their
            # two-argument interface and historical estimator-value fallback.
            hook = getattr(self.congestion_control, "ack_received_bytes", None)
            if hook is None:
                self.congestion_control.ack_received(rtt, self.env.now)
            else:
                hook(sequence - previous_ack, sample, self.env.now)
        if self.debug:
            print(
                f"TCP {self.element_id} ACK={self.last_ack}, "
                f"cwnd={self.congestion_control.cwnd:.1f} at {self.env.now:.4f}."
            )
        self._wake_sender()
