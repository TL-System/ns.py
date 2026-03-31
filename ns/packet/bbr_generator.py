"""
Implements a packet generator that simulates the TCP protocol, including support for
various congestion control mechanisms.
"""

import copy
from dataclasses import dataclass

import simpy

from ns.packet.packet import Packet
from ns.packet.rate_sample import Connection, RateSample
from ns.utils.timer import Timer


@dataclass
class SegmentState:
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


class BBRPacketGenerator:
    """Generates packets with a simulated TCP protocol.

    Parameters
    ----------
    env: simpy.Environment
        The simulation environment.
    flow: Flow
        The flow that serves as the source (eventually, this should be a list).
    element_id: str
        The ID for this element.
    rec_flow: bool
        Are we recording the statistics of packets generated?
    rate_sample: RateSample
    """

    def __init__(
        self,
        env,
        flow,
        cc,
        element_id=None,
        rtt_estimate=0.14,
        granularity=0.01,
        debug=True,
    ):
        self.element_id = element_id
        self.env = env
        self.out = None
        self.flow = flow
        self.granularity = granularity
        self.congestion_control = cc
        self.congestion_control.rs = RateSample()
        self.congestion_control.C = Connection()
        self.packet_in_flight = 0

        self.mss = 512  # maximum segment size, in bytes
        self.last_arrival = 0  # the time when data last arrived from the flow

        # the next sequence number to be sent, in bytes
        self.next_seq = 0
        # the maximum sequence number in the in-transit data buffer
        self.send_buffer = self.flow.init_send_buffer()
        # the sequence number of the segment that is last acknowledged
        self.last_ack = 0
        # the maximum sequence number of the segment that is acknowledged
        self.max_ack = 0
        # the count of duplicate acknolwedgments
        self.dupack = 0
        # the RTT estimate
        self.rtt_estimate = rtt_estimate
        # the retransmission timeout
        self.rto = self.rtt_estimate * 2
        # an estimate of the RTT deviation
        self.est_deviation = 0
        # whether or not space in the congestion window is available
        self.cwnd_available = simpy.Store(env)

        # In-flight data is keyed by logical segment start sequence number.
        # The transport rewrite keeps retransmission timing and delivery-rate
        # metadata in sender-owned state and preserves Packet.time as the
        # original first-transmit timestamp seen by sinks.
        self.sent_packets = {}
        self.segment_state = {}

        self.timer = None
        self.to_pkt_id = 0

        self.action = env.process(self.run())
        self.debug = debug

    def _build_packet(self, state):
        """Create a fresh packet attempt from sender-owned segment state."""
        packet = Packet(
            state.first_tx_time,
            state.size,
            state.seq,
            src=self.flow.src,
            flow_id=self.flow.fid,
            tx_in_flight=state.tx_in_flight,
        )
        packet.first_sent_time = state.first_sent_time
        packet.delivered_time = state.delivered_time
        packet.delivered = state.delivered
        packet.lost = state.lost
        packet.is_app_limited = state.is_app_limited
        return packet

    def _get_segment_state(self, packet_id):
        """Return sender-owned state for an outstanding BBR segment."""
        state = self.segment_state.get(packet_id)
        if state is not None:
            return state

        packet = self.sent_packets[packet_id]
        state = SegmentState(
            seq=packet.packet_id,
            size=packet.size,
            first_tx_time=packet.time,
            last_tx_time=packet.time,
            first_sent_time=packet.first_sent_time,
            delivered_time=packet.delivered_time,
            delivered=packet.delivered,
            lost=packet.lost,
            is_app_limited=packet.is_app_limited,
            tx_in_flight=packet.tx_in_flight,
        )
        self.segment_state[packet_id] = state
        return state

    def _send_new_packet(self, packet_size):
        """Send a new BBR data packet and register its sender-owned state."""
        packet = Packet(
            self.env.now,
            packet_size,
            self.next_seq,
            src=self.flow.src,
            flow_id=self.flow.fid,
            tx_in_flight=self.packet_in_flight,
        )
        self.congestion_control.rs.send_packet(
            packet,
            self.congestion_control.C,
            self.max_ack - self.next_seq,
            self.env.now,
        )
        self.congestion_control.next_departure_time = self.env.now
        if self.congestion_control.pacing_rate > 0:
            self.congestion_control.next_departure_time += (
                packet.size / self.congestion_control.pacing_rate
            )

        self.sent_packets[packet.packet_id] = packet
        self.segment_state[packet.packet_id] = SegmentState(
            seq=packet.packet_id,
            size=packet.size,
            first_tx_time=packet.time,
            last_tx_time=self.env.now,
            first_sent_time=packet.first_sent_time,
            delivered_time=packet.delivered_time,
            delivered=packet.delivered,
            lost=packet.lost,
            is_app_limited=packet.is_app_limited,
            tx_in_flight=packet.tx_in_flight,
        )
        self.packet_in_flight += packet.size
        if self.debug:
            print(
                f"Send packet {packet.packet_id} with size {packet.size}, "
                f"flow_id {packet.flow_id} at time {self.env.now:.4f}, "
                f"and the packet delivered time is {packet.delivered_time:.4f}."
            )
        self.out.put(packet)

        self.next_seq += packet.size

        self.congestion_control.C.check_if_application_limited(
            self.next_seq, self.mss, self.packet_in_flight
        )

        if self.timer is None:
            self.timer = Timer(self.env, 0, self.timeout_callback, self.rto)
            self.to_pkt_id = packet.packet_id

        if self.debug:
            print(
                f"Setting a timer for packet {packet.packet_id} with an RTO"
                f" of {self.rto:.4f}."
            )

    def _retransmit_packet(self, packet_id):
        """Emit a fresh retransmission attempt for an outstanding segment."""
        state = self._get_segment_state(packet_id)
        state.retransmit_count += 1
        state.last_tx_time = self.env.now
        state.tx_in_flight = self.packet_in_flight
        resent_pkt = self._build_packet(state)
        self.sent_packets[packet_id] = resent_pkt
        return resent_pkt

    def _restart_oldest_timer(self):
        """Point the retransmission timer at the oldest outstanding segment."""
        if not self.segment_state:
            if self.timer is not None:
                self.timer.stop()
                self.timer = None
            self.to_pkt_id = 0
            return

        oldest_packet_id = min(self.segment_state)
        self.to_pkt_id = oldest_packet_id
        if self.timer is None:
            self.timer = Timer(self.env, 0, self.timeout_callback, self.rto)
        self.timer.restart(self.rto, self.segment_state[oldest_packet_id].last_tx_time)

    def update_next_seq(self):
        self.send_buffer += self.flow.next_send_buffer(self.env.now)
        self.congestion_control.C.write_seq = self.send_buffer + 1
        self.congestion_control.C.check_if_application_limited(
            self.next_seq, self.mss, self.packet_in_flight
        )

    def run(self):
        # FIle download, video, game
        """The generator function used in simulations."""
        if self.flow.start_time:
            yield self.env.timeout(self.flow.start_time)

        while self.env.now < self.flow.finish_time:
            if self.flow.size is not None and self.next_seq >= self.flow.size:
                return

            while self.next_seq >= self.send_buffer:
                # retrieving more packets from the (application-layer) flow
                if self.flow.arrival_dist is not None:
                    # if the flow has an arrival distribution, wait for the next arrival
                    wait_time = self.flow.arrival_dist() - (
                        self.env.now - self.last_arrival
                    )
                    if wait_time > 0:
                        yield self.env.timeout(wait_time)

            self.update_next_seq()
            # the sender can transmit up to the size of the congestion window
            if self.env.now - self.congestion_control.next_departure_time < 0:
                yield self.env.timeout(
                    self.congestion_control.next_departure_time - self.env.now
                )
            send_limit = min(self.send_buffer, self.last_ack + self.congestion_control.cwnd)
            available_bytes = send_limit - self.next_seq
            if available_bytes <= 0:
                self.congestion_control.C.is_cwnd_limited = True
                yield self.cwnd_available.get()
            else:
                self._send_new_packet(min(self.mss, available_bytes))

    def timeout_callback(self, packet_id=0):
        """To be called when a timer expired for a packet with 'packet_id'."""
        self.update_next_seq()
        if not self.segment_state:
            if not self.sent_packets:
                return
        packet_id = self.to_pkt_id or min(self.sent_packets)
        state = self._get_segment_state(packet_id)
        if self.debug:
            print(
                f"Timer expired for packet {packet_id} {self.flow.fid} "
                f"at time {self.env.now:.4f}."
            )

        self.congestion_control.C.lost += state.size

        self.congestion_control.set_before_control(self.env.now, self.packet_in_flight)
        self.congestion_control.timer_expired(self.sent_packets[packet_id])

        # retransmitting the segment
        resent_pkt = self._retransmit_packet(packet_id)
        self.out.put(resent_pkt)
        self.rto *= 2
        if self.rto > 60:
            self.rto = 60
        if self.debug:
            print(
                f"to Resending packet {resent_pkt.packet_id} with flow_id {resent_pkt.flow_id} "
                f"at time {self.env.now:.4f} with a timeout time {self.env.now + self.rto:4f}."
            )

        # starting a new timer for this segment and doubling the retransmission timeout
        self.timer.restart(self.rto, self.segment_state[packet_id].last_tx_time)
        self.to_pkt_id = packet_id

        self.congestion_control.C.check_if_application_limited(
            self.next_seq, self.mss, self.packet_in_flight
        )

    def put(self, ack):
        """On receiving an acknowledgment packet."""
        self.update_next_seq()
        self.congestion_control.C.check_if_application_limited(
            self.next_seq, self.mss, self.packet_in_flight
        )

        # ACK RTT follows the acknowledged segment's transport timestamp.
        # first_sent_time remains the flight-level marker for RateSample only.
        sample_rtt = self.env.now - ack.time
        self.congestion_control.rs.newly_acked = ack.ack - self.last_ack

        if ack.ack == self.last_ack:
            temp_pkt = copy.copy(ack)
            temp_pkt.size = self.mss

            self.congestion_control.rs.updaterate_sample(
                temp_pkt, self.congestion_control.C, self.env.now
            )
            self.congestion_control.rs.update_sample_group(
                self.congestion_control.C, sample_rtt
            )
            if ack.ack < self.next_seq:
                self.dupack += 1
        else:
            # fast recovery in RFC 2001 and TCP Reno
            self.congestion_control.dupack_over()
            self.dupack = 0

        # RFC 6298 Update on rto
        if self.max_ack == 0:
            self.rtt_estimate = sample_rtt
            self.est_deviation = sample_rtt / 2
            self.rto = min(
                self.rtt_estimate + max(4 * self.est_deviation, self.granularity), 60
            )
            self.rto = max(self.rto, 1)
        else:
            sample_err = self.rtt_estimate - sample_rtt
            self.est_deviation = (3 * self.est_deviation + sample_err) / 4
            self.rtt_estimate = (7 * self.rtt_estimate + sample_rtt) / 8
            self.rto = min(
                self.rtt_estimate + max(4 * self.est_deviation, self.granularity), 60
            )
            self.rto = max(self.rto, 1)

        self.max_ack = max(self.max_ack, ack.ack)

        if self.dupack == 2:
            self.congestion_control.C.lost += self._get_segment_state(ack.ack).size

            self.congestion_control.set_before_control(
                self.env.now, self.packet_in_flight
            )
            self.congestion_control.consecutive_dupacks_received(
                self.sent_packets[ack.ack]
            )
            self.congestion_control.ack_received(sample_rtt, self.env.now)

            resent_pkt = self._retransmit_packet(ack.ack)

            if self.debug:
                print(
                    f"dup Resending packet {resent_pkt.packet_id} with flow_id "
                    f"{resent_pkt.flow_id} at time {self.env.now:.4f}."
                )
            self.out.put(resent_pkt)

        elif self.dupack > 2:
            self.congestion_control.set_before_control(
                self.env.now, self.packet_in_flight
            )
            self.congestion_control.ack_received(sample_rtt, self.env.now)
            self.congestion_control.more_dupacks_received(self.sent_packets[ack.ack])

        elif self.dupack == 0:
            self.congestion_control.set_before_control(
                self.env.now, self.packet_in_flight
            )

            acked_packet_ids = []
            for packet_id in sorted(self.sent_packets):
                state = self._get_segment_state(packet_id)
                if packet_id + state.size <= ack.ack:
                    acked_packet_ids.append(packet_id)

            bbr_update = bool(acked_packet_ids)
            for packet_id in sorted(acked_packet_ids):
                packet = self.sent_packets[packet_id]
                if packet.delivered_time:
                    self.packet_in_flight -= packet.size
                self.congestion_control.rs.updaterate_sample(
                    packet, self.congestion_control.C, self.env.now
                )

            self.congestion_control.rs.update_sample_group(
                self.congestion_control.C, sample_rtt
            )

            self.congestion_control.rs.full_lost = 0
            last_packet_lost = -self.mss * 2

            for id, packet in self.sent_packets.items():
                if packet.self_lost:
                    if id - last_packet_lost > self.mss:
                        self.congestion_control.rs.full_lost += 1
                    last_packet_lost = id

            if ack.ack > self.max_ack:
                self.max_ack = ack.ack

            self.last_ack = ack.ack

            if self.debug:
                print(
                    f"Ack received till sequence number {ack.ack} at time "
                    f"{self.env.now:.4f}."
                )
                print(
                    f"Congestion window size = {self.congestion_control.cwnd:.1f}, "
                    f"last ack = {self.last_ack}."
                )

            if bbr_update:
                self.congestion_control.ack_received(sample_rtt, self.env.now)

            for packet_id in sorted(acked_packet_ids):
                del self.sent_packets[packet_id]
                del self.segment_state[packet_id]

            if self.max_ack == self.next_seq and self.timer is not None:
                self.timer.stop()
                del self.timer
                self.timer = None
            elif acked_packet_ids:
                self._restart_oldest_timer()

            self.congestion_control.C.is_cwnd_limited = False
            self.cwnd_available.put(True)
