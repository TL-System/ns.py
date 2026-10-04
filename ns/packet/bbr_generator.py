"""A paced TCP sender with BBR control and sender-owned segment accounting."""

from dataclasses import dataclass
import math

import simpy

from ns.flow.flow import AppType
from ns.packet.packet import Packet
from ns.packet.rate_sample import Connection, RateSample
from ns.utils.timer import Timer


@dataclass
class SegmentState:
    """One unacknowledged byte range; packet attempts never own this state.

    Transport timestamps belong here. Delivery-rate metadata records the flight
    at the original send and is copied into attempts for BBR's separate sampler.
    A partial ACK shortens this range without changing its original send time.
    """

    seq: int
    size: int
    first_tx_time: float
    last_tx_time: float
    first_sent_time: float = 0.0
    delivered_time: float = 0.0
    delivered: int = 0
    lost: int = 0
    is_app_limited: bool = False
    tx_in_flight: int = 0
    retransmit_count: int = 0
    self_lost: bool = False
    partial_acked: bool = False


class BBRPacketGenerator:
    """Send application bytes with a congestion window and BBR pacing.

    Sizes, sequences and windows count bytes; BBR's pacing rate is bytes/second.
    ``finish_time`` is an exclusive deadline for new data. Already emitted bytes
    remain reliable after that deadline; ``None`` imposes no deadline.
    """

    def __init__(
        self, env, flow, cc, element_id=None, rtt_estimate=0.14,
        granularity=0.001, debug=True,
    ):
        self.element_id = element_id
        self.env = env
        self.out = None
        self.flow = flow
        self.debug = debug
        self.granularity = granularity
        self.congestion_control = cc
        cc.rs = RateSample()
        cc.C = Connection()
        self.mss = self._byte_count(getattr(cc, "mss", 512))
        if flow.size is not None:
            self._byte_count(flow.size, allow_zero=True)
        if not math.isfinite(rtt_estimate) or rtt_estimate <= 0:
            raise ValueError("rtt_estimate must be finite and positive")
        if not math.isfinite(granularity) or granularity <= 0:
            raise ValueError("granularity must be finite and positive")
        self.packet_in_flight = 0
        # Flight counts unique unacknowledged bytes, including a partial suffix.
        # Retransmitting the same bytes never adds a second copy to this count.
        self.next_seq = 0
        self.last_ack = 0
        self.max_ack = 0
        self.dupack = 0
        self.recovery_high_sequence = None
        self.rtt_estimate = rtt_estimate
        self.est_deviation = 0
        self._rtt_initialized = False
        # Align the initial timer, learned timer floor and backoff cap with Days:
        # one to sixty seconds, with a default clock granularity of one ms.
        self.rto = min(60, max(1, rtt_estimate * 2))
        self.cwnd_available = simpy.Store(env, capacity=1)
        self.sent_packets = {}
        self.segment_state = {}
        self.timer = None
        self.to_pkt_id = 0

        self.last_arrival = max(env.now, flow.start_time or 0)
        # App writes are byte-frontier updates, not individual wire packets.
        # Keep each pending arrival draw until its scheduled time is reached.
        self._next_application_time = None
        self.send_buffer = (
            int(flow.size or 0) if flow.typ == AppType.BULK_TRANSFER else 0
        )
        cc.C.write_seq = self.send_buffer
        self.action = env.process(self.run())

    @staticmethod
    def _byte_count(value, allow_zero=False, round_down=False):
        """TCP byte positions are integral, unlike generic queue packet sizes."""
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or (not round_down and int(value) != value)
                or value < (0 if allow_zero else 1)):
            raise ValueError("TCP byte counts must be integral and positive")
        return int(value)

    def _build_packet(self, state):
        """Create an attempt, preserving the original latency timestamp."""
        packet = Packet(
            state.first_tx_time, state.size, state.seq, src=self.flow.src,
            dst=self.flow.dst, flow_id=self.flow.fid,
            tx_in_flight=state.tx_in_flight,
        )
        packet.first_sent_time = state.first_sent_time
        packet.delivered_time = state.delivered_time
        packet.delivered = state.delivered
        packet.lost = state.lost
        packet.is_app_limited = state.is_app_limited
        packet.self_lost = state.self_lost
        return packet

    def _restart_oldest_timer(self):
        """RFC 6298: one timer, rearmed from now when the ACK advances."""
        if not self.segment_state:
            if self.timer is not None:
                self.timer.stop()
            self.timer = None
            self.to_pkt_id = 0
            return
        self.to_pkt_id = min(self.segment_state)
        if self.timer is None:
            self.timer = Timer(self.env, 0, self.timeout_callback, self.rto)
        else:
            self.timer.restart(self.rto)

    def _send_new_packet(self, packet_size):
        """Register every byte and the timer before synchronous forwarding."""
        packet_size = self._byte_count(packet_size)
        state = SegmentState(
            self.next_seq, packet_size, self.env.now, self.env.now,
            tx_in_flight=self.packet_in_flight + packet_size,
        )
        packet = self._build_packet(state)
        self.congestion_control.rs.send_packet(
            packet, self.congestion_control.C, self.packet_in_flight, self.env.now,
        )
        state.first_sent_time = packet.first_sent_time
        state.delivered_time = packet.delivered_time
        state.delivered = packet.delivered
        state.lost = packet.lost
        state.is_app_limited = packet.is_app_limited
        self.segment_state[state.seq] = state
        self.sent_packets[state.seq] = packet
        # A zero-delay downstream receiver may call put(ACK) inside out.put().
        # All sender accounting must already describe this emitted segment.
        self.next_seq += packet_size
        self.packet_in_flight += packet_size
        # Controller pacing uses bytes/s; link ports separately convert bytes
        # to bits when dividing by their bits/s line rates.
        self.congestion_control.next_departure_time = self.env.now
        if self.congestion_control.pacing_rate > 0:
            self.congestion_control.next_departure_time += (
                packet_size / self.congestion_control.pacing_rate
            )
        if self.timer is None:
            self._restart_oldest_timer()
        self.congestion_control.C.check_if_application_limited(
            self.next_seq, self.mss, self.packet_in_flight,
        )
        if self.debug:
            print(f"BBR sends {state.seq}+{state.size} at {self.env.now:.4f}")
        self.out.put(packet)
        return packet

    def _retransmit_packet(self, packet_id):
        """Replace only the packet attempt; outstanding bytes do not increase."""
        state = self.segment_state[packet_id]
        state.retransmit_count += 1
        state.last_tx_time = self.env.now
        state.tx_in_flight = self.packet_in_flight
        packet = self._build_packet(state)
        self.sent_packets[packet_id] = packet
        return packet

    def _schedule_application_arrival(self):
        interval = (
            self.flow.arrival_dist() if self.flow.arrival_dist else self.granularity
        )
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("application intervals must be finite and positive")
        self._next_application_time = self.last_arrival + interval

    def update_next_seq(self):
        """Accept scheduled application writes once, never by redrawing on ACKs."""
        if self.flow.typ == AppType.BULK_TRANSFER:
            if self.flow.size is None and self.send_buffer <= self.next_seq:
                self.send_buffer += self.mss
        else:
            if self._next_application_time is None:
                self._schedule_application_arrival()
            while (self._next_application_time <= self.env.now
                   and (self.flow.finish_time is None
                        or self._next_application_time < self.flow.finish_time)
                   and (self.flow.size is None or self.send_buffer < self.flow.size)):
                # Continuous size distributions are quantized once per write;
                # segmentation afterward never creates fractional TCP bytes.
                size = self._byte_count(
                    self.flow.size_dist() if self.flow.size_dist else self.mss,
                    round_down=True,
                )
                if self.flow.size is not None:
                    size = min(size, int(self.flow.size) - self.send_buffer)
                self.send_buffer += size
                self.last_arrival = self._next_application_time
                if self.flow.size is not None and self.send_buffer >= self.flow.size:
                    break
                self._schedule_application_arrival()
        self.congestion_control.C.write_seq = self.send_buffer
        self.congestion_control.C.check_if_application_limited(
            self.next_seq, self.mss, self.packet_in_flight,
        )

    def run(self):
        """Wait for app writes, pacing, or ACK space; recheck every deadline."""
        if self.flow.start_time is not None and self.flow.start_time > self.env.now:
            yield self.env.timeout(self.flow.start_time - self.env.now)
        deadline = self.flow.finish_time
        while deadline is None or self.env.now < deadline:
            if self.flow.size is not None and self.next_seq >= self.flow.size:
                return
            self.update_next_seq()
            if self.next_seq >= self.send_buffer:
                wake = self._next_application_time
                if deadline is not None:
                    wake = min(wake, deadline)
                yield self.env.timeout(max(0, wake - self.env.now))
                continue
            departure = self.congestion_control.next_departure_time
            if departure > self.env.now:
                if deadline is not None:
                    departure = min(departure, deadline)
                yield self.env.timeout(departure - self.env.now)
                continue
            # A fractional cwnd allows only its whole-byte prefix on the wire.
            available = math.floor(self.congestion_control.cwnd) - self.packet_in_flight
            self.congestion_control.C.is_cwnd_limited = available <= 0
            if available > 0:
                self._send_new_packet(min(self.mss, available,
                                          self.send_buffer - self.next_seq))
            else:
                ready = self.cwnd_available.get()
                if deadline is None:
                    yield ready
                else:
                    yield ready | self.env.timeout(deadline - self.env.now)
                    if not ready.triggered:
                        # Leaving an abandoned Store.get would steal a later
                        # ACK wakeup after the new-data deadline has passed.
                        ready.cancel()

    def timeout_callback(self, packet_id=0):
        """Declare the oldest attempt lost, back off and rearm before sending."""
        if not self.sent_packets:
            self._restart_oldest_timer()
            return
        packet_id = min(self.sent_packets)
        state = self.segment_state[packet_id]
        self.congestion_control.C.lost += state.size
        self.dupack = 0
        if self.recovery_high_sequence is not None:
            self.congestion_control.dupack_over()
        self.recovery_high_sequence = None
        self.congestion_control.set_before_control(self.env.now, self.packet_in_flight)
        # The controller receives its own metadata object, never a queued attempt.
        self.congestion_control.timer_expired(self._build_packet(state))
        packet = self._retransmit_packet(packet_id)
        self.rto = min(60, self.rto * 2)
        # Rearm before forwarding: an immediate ACK can safely cancel it.
        self._restart_oldest_timer()
        self.out.put(packet)

    def _update_rto(self, sample):
        """RFC 6298 deviation uses the previous SRTT and an absolute error."""
        if not self._rtt_initialized:
            self.rtt_estimate = sample
            self.est_deviation = sample / 2
            self._rtt_initialized = True
        else:
            self.est_deviation = (3 * self.est_deviation
                                  + abs(self.rtt_estimate - sample)) / 4
            self.rtt_estimate = (7 * self.rtt_estimate + sample) / 8
        self.rto = min(60, max(1, self.rtt_estimate
                              + max(4 * self.est_deviation, self.granularity)))

    def put(self, ack):
        """Consume valid cumulative ACK bytes; ignore stale or unrelated ACKs."""
        frontier = ack.ack
        if (ack.flow_id != self.flow.fid + 10000
                or isinstance(frontier, bool) or not isinstance(frontier, int)
                or frontier < self.last_ack or frontier > self.next_seq
                or not self.sent_packets):
            return
        rs = self.congestion_control.rs
        rs.newly_acked = frontier - self.last_ack
        if frontier == self.last_ack:
            self.dupack += 1
            self.congestion_control.set_before_control(
                self.env.now, self.packet_in_flight,
            )
            if self.dupack == 3 and self.recovery_high_sequence is None:
                # Three duplicate ACKs identify one loss episode. Additional
                # duplicates do not retransmit the same missing range again.
                self.recovery_high_sequence = self.next_seq
                state = self.segment_state[min(self.segment_state)]
                self.congestion_control.C.lost += state.size
                self.congestion_control.consecutive_dupacks_received(
                    self._build_packet(state),
                )
                packet = self._retransmit_packet(state.seq)
                self._restart_oldest_timer()
                self.out.put(packet)
            elif self.dupack > 3:
                state = self.segment_state[min(self.segment_state)]
                self.congestion_control.more_dupacks_received(self._build_packet(state))
            self._wake_sender()
            return

        oldest = self.segment_state[min(self.segment_state)]
        sample = 0
        # Without timestamps/SACK, sample exactly one complete unretransmitted
        # segment. Cumulative/partial ACKs and retransmissions are ambiguous.
        if (oldest.seq == self.last_ack and frontier == oldest.seq + oldest.size
                and oldest.retransmit_count == 0 and not oldest.partial_acked):
            sample = self.env.now - oldest.first_tx_time
            # A synchronous ACK has a valid zero RTT; the RTO floor still applies.
            self._update_rto(sample)
        for packet_id in sorted(list(self.segment_state)):
            state = self.segment_state[packet_id]
            acknowledged = min(state.size, max(0, frontier - state.seq))
            if not acknowledged:
                break
            # A local copy keeps sampling's consumed marker off emitted packets.
            packet = self._build_packet(state)
            packet.size = acknowledged
            rs.updaterate_sample(packet, self.congestion_control.C, self.env.now)
            del self.sent_packets[packet_id]
            del self.segment_state[packet_id]
            if acknowledged < state.size:
                state.seq += acknowledged
                state.size -= acknowledged
                # A suffix no longer represents one complete RTT observation.
                state.partial_acked = True
                self.segment_state[state.seq] = state
                self.sent_packets[state.seq] = self._build_packet(state)
        self.packet_in_flight -= rs.newly_acked
        self.last_ack = self.max_ack = frontier
        self.dupack = 0
        # Instantaneous synchronous ACKs have no interval to divide by. Full
        # estimator validity and retransmit sampling are audited in Phase 5.
        if max(rs.ack_elapsed, rs.send_elapsed) > 0:
            rs.update_sample_group(
                self.congestion_control.C, sample if sample > 0 else -1,
            )
        rs.full_lost = 0
        # BBR controls the actual remaining flight after this ACK. Classic TCP
        # instead passes pre-ACK flight for its loss-window controller contract.
        self.congestion_control.set_before_control(self.env.now, self.packet_in_flight)
        self.congestion_control.ack_received(sample, self.env.now)
        self._restart_oldest_timer()
        if self.recovery_high_sequence is not None:
            if frontier >= self.recovery_high_sequence:
                self.recovery_high_sequence = None
                self.congestion_control.dupack_over()
            elif self.segment_state:
                # A partial recovery ACK exposes the next hole. Keep the same
                # recovery frontier until all bytes of that flight are covered.
                state = self.segment_state[min(self.segment_state)]
                self.env.process(self._retransmit_after_ack(
                    state, state.seq, state.retransmit_count,
                ))
        self.congestion_control.C.is_cwnd_limited = False
        self._wake_sender()

    def _retransmit_after_ack(self, state, sequence, retransmit_count):
        """Yield one turn so synchronous recovery ACKs cannot recurse forever."""
        yield self.env.timeout(0)
        # Another ACK or timeout may retire, trim or retransmit this range before
        # its turn. Record an attempt only when it still needs to go on the wire.
        if (self.segment_state.get(sequence) is state
                and self.last_ack == sequence
                and self.recovery_high_sequence is not None
                and state.retransmit_count == retransmit_count):
            self.congestion_control.C.lost += state.size
            packet = self._retransmit_packet(sequence)
            # All attempt metadata and timer state precede synchronous ACKs.
            self._restart_oldest_timer()
            self.out.put(packet)

    def _wake_sender(self):
        """Coalesce ACK wakeups rather than retaining one token per packet."""
        if not self.cwnd_available.items:
            self.cwnd_available.put(True)
