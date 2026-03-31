"""
Implements a packet generator that simulates the TCP protocol, including support
for various congestion control mechanisms.
"""

from dataclasses import dataclass

import simpy

from ns.packet.packet import Packet
from ns.utils.timer import Timer


@dataclass
class SegmentState:
    seq: int
    size: int
    first_tx_time: float
    last_tx_time: float
    retransmit_count: int = 0
    timer: Timer = None


class TCPPacketGenerator:
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
    """

    def __init__(self, env, flow, cc, element_id=None, debug=False):
        self.element_id = element_id
        self.env = env
        self.out = None
        self.flow = flow
        self.congestion_control = cc

        self.mss = 512  # maximum segment size, in bytes
        self.last_arrival = 0  # the time when data last arrived from the flow

        # the next sequence number to be sent, in bytes
        self.next_seq = 0
        # the maximum sequence number in the in-transit data buffer
        self.send_buffer = 0
        # the sequence number of the segment that is last acknowledged
        self.last_ack = 0
        # the count of duplicate acknolwedgments
        self.dupack = 0
        # deviation of the RTT
        self.rtt_var = 0.0
        # smoothed RTT
        self.smoothed_rtt = 0.0
        # the retransmission timeout
        self.rto = 1.0
        # the most recent RTT sample that was accepted as unambiguous
        self.last_rtt_sample = 0.0
        # whether or not space in the congestion window is available
        self.cwnd_available = simpy.Store(env)

        # Timers are keyed by the logical segment start sequence number.
        # Follow-on rewrite steps keep retransmission state in sender-owned
        # segment metadata rather than in mutable Packet objects.
        self.timers = {}
        # In-flight data is currently keyed by segment start sequence number.
        # ACK cleanup must eventually use segment-end semantics
        # (seq + size <= ack), and each retransmission attempt must emit a
        # fresh Packet while preserving the original Packet.time.
        self.sent_packets = {}
        self.segment_state = {}

        self.action = env.process(self.run())
        self.debug = debug

    def _get_segment_state(self, packet_id):
        """Return sender-owned logical state for a segment, creating it lazily."""
        state = self.segment_state.get(packet_id)
        if state is not None:
            return state

        packet = self.sent_packets[packet_id]
        state = SegmentState(
            seq=packet.packet_id,
            size=packet.size,
            first_tx_time=packet.time,
            last_tx_time=packet.time,
            timer=self.timers.get(packet_id),
        )
        self.segment_state[packet_id] = state
        return state

    def _build_packet(self, state):
        """Create a fresh packet attempt from sender-owned segment state."""
        return Packet(
            state.first_tx_time,
            state.size,
            state.seq,
            src=self.flow.src,
            flow_id=self.flow.fid,
        )

    def _send_new_packet(self, packet_size):
        """Send a fresh data packet and register sender-owned state for it."""
        packet = Packet(
            self.env.now,
            packet_size,
            self.next_seq,
            src=self.flow.src,
            flow_id=self.flow.fid,
        )

        self.sent_packets[packet.packet_id] = packet
        self.segment_state[packet.packet_id] = SegmentState(
            seq=packet.packet_id,
            size=packet.size,
            first_tx_time=packet.time,
            last_tx_time=packet.time,
        )

        if self.debug:
            print(
                f"TCPPacketGenerator {self.element_id} sent packet {packet.packet_id} "
                f"with size {packet.size}, flow_id {packet.flow_id} at "
                f"time {self.env.now:.4f}."
            )

        self.out.put(packet)

        self.next_seq += packet.size
        timer = Timer(
            self.env,
            timer_id=packet.packet_id,
            timeout_callback=self.timeout_callback,
            rto=self.rto,
        )
        self.timers[packet.packet_id] = timer
        self.segment_state[packet.packet_id].timer = timer

        if self.debug:
            print(
                f"TCPPacketGenerator {self.element_id} is setting a timer "
                f"for packet {packet.packet_id} with an RTO of {self.rto:.4f}."
            )

        return packet

    def run(self):
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
                    self.last_arrival = self.env.now

                packet_size = 0
                if self.flow.size_dist is not None:
                    packet_size = self.flow.size_dist()
                else:
                    if self.flow.size is not None:
                        packet_size = min(self.mss, self.flow.size - self.next_seq)
                    else:
                        packet_size = self.mss
                self.send_buffer += packet_size

            # The sender can transmit any positive byte count up to the smaller
            # of the buffered data and the available congestion window.
            send_limit = min(self.send_buffer, self.last_ack + self.congestion_control.cwnd)
            available_bytes = send_limit - self.next_seq
            if available_bytes > 0:
                packet_size = min(self.mss, available_bytes)
                self._send_new_packet(packet_size)
            else:
                # No further space in the congestion window to transmit packets
                # at this time, waiting for acknowledgements
                yield self.cwnd_available.get()

    def timeout_callback(self, packet_id=0):
        """To be called when a timer expired for a packet with 'packet_id'."""
        if self.debug:
            print(
                f"TCPPacketGenerator {self.element_id}'s Timer expired for packet "
                f"{packet_id} at time {self.env.now:.4f}."
            )

        self.congestion_control.timer_expired()

        # retransmitting the segment
        state = self._get_segment_state(packet_id)
        state.retransmit_count += 1
        state.last_tx_time = self.env.now
        resent_pkt = self._build_packet(state)
        self.sent_packets[packet_id] = resent_pkt
        self.out.put(resent_pkt)

        if self.debug:
            print(
                f"TCPPacketGenerator {self.element_id} is resending packet {resent_pkt.packet_id} "
                f"with flow_id {resent_pkt.flow_id} at time {self.env.now:.4f}."
            )

        # starting a new timer for this segment and doubling the retransmission timeout
        revised_rto = self.timers[packet_id].rto * 2
        state.timer = self.timers[packet_id]
        state.timer.restart(revised_rto)

    def put(self, ack):
        """On receiving an acknowledgment packet."""
        assert ack.flow_id >= 10000  # the received packet must be an ack
        previous_ack = self.last_ack
        previous_segment = self.segment_state.get(previous_ack)

        if ack.ack == self.last_ack:
            self.dupack += 1
        else:
            # fast recovery in RFC 2001 and TCP Reno
            if self.dupack > 0:
                self.congestion_control.dupack_over()
                self.dupack = 0

        if self.dupack >= 3:
            if self.dupack == 3:
                self.congestion_control.consecutive_dupacks_received()

            state = self._get_segment_state(ack.ack)
            state.retransmit_count += 1
            state.last_tx_time = self.env.now
            resent_pkt = self._build_packet(state)
            self.sent_packets[ack.ack] = resent_pkt
            if self.debug:
                print(
                    f"TCPPacketGenerator {self.element_id} is resending packet "
                    f"{resent_pkt.packet_id} with flow_id {resent_pkt.flow_id} at time "
                    f"{self.env.now:.4f}."
                )

            self.out.put(resent_pkt)

            if self.dupack > 3:
                self.congestion_control.more_dupacks_received()

                if self.last_ack + self.congestion_control.cwnd >= ack.ack:
                    send_limit = min(
                        self.send_buffer,
                        self.last_ack + self.congestion_control.cwnd,
                    )
                    available_bytes = send_limit - self.next_seq
                    if available_bytes > 0:
                        self._send_new_packet(min(self.mss, available_bytes))

            return

        if self.dupack == 0:
            # Only accept RTT samples for exactly one un-retransmitted segment.
            eligible_rtt_sample = False
            sample_rtt = 0.0
            if (
                ack.ack > previous_ack
                and previous_segment is not None
                and ack.ack == previous_ack + previous_segment.size
                and previous_segment.retransmit_count == 0
            ):
                eligible_rtt_sample = True
                sample_rtt = self.env.now - previous_segment.first_tx_time

            # Authoritative sources for RTO calculation

            # RFC 6298: Computing TCP's Retransmission Timer

            # This RFC specifically focuses on the RTO algorithm and updates the
            # way RTO is calculated. It obsoletes the RTO calculation described
            # in RFC 2988. The updated algorithm is commonly referred to as the
            # "Karn/Partridge Algorithm."

            alpha = 0.125
            beta = 0.25

            if eligible_rtt_sample:
                # calculates the deviation (RTTVAR) of the RTT to account for
                # variations in the network
                if self.rtt_var == 0.0:
                    self.rtt_var = sample_rtt / 2.0
                else:
                    deviation = self.smoothed_rtt - sample_rtt
                    self.rtt_var = (1.0 - beta) * self.rtt_var + beta * abs(
                        deviation
                    )

                # computes a smoothed round-trip time (SRTT)
                if self.smoothed_rtt == 0.0:
                    self.smoothed_rtt = sample_rtt
                else:
                    self.smoothed_rtt = (
                        1.0 - alpha
                    ) * self.smoothed_rtt + alpha * sample_rtt
                self.rto = max(1.0, self.smoothed_rtt + 4.0 * self.rtt_var)
                self.last_rtt_sample = sample_rtt

            self.last_ack = ack.ack
            if eligible_rtt_sample:
                rtt_for_cc = sample_rtt
            else:
                rtt_for_cc = self.smoothed_rtt
                if rtt_for_cc == 0.0:
                    rtt_for_cc = self.last_rtt_sample
            self.congestion_control.ack_received(rtt_for_cc, self.env.now)

            if self.debug:
                print(
                    f"TCPPacketGenerator {self.element_id} received ack till sequence number "
                    f"{ack.ack} at time {self.env.now:.4f}."
                )
                print(
                    f"TCPPacketGenerator {self.element_id} congestion window size = "
                    f"{self.congestion_control.cwnd:.1f}, last ack = {self.last_ack}."
                )

            # this acknowledgment should acknowledge all the intermediate
            # segments sent between the lost packet and the receipt of the
            # first duplicate ACK, if any
            acked_packets = []
            for packet_id, state in self.segment_state.items():
                if packet_id + state.size <= ack.ack:
                    acked_packets.append(packet_id)

            for packet_id in sorted(acked_packets):
                if self.debug:
                    print(
                        f"TCPPacketGenerator {self.element_id} stopped timer "
                        f"{packet_id} at time {self.env.now:.4f}."
                    )
                self.segment_state[packet_id].timer.stop()
                del self.timers[packet_id]
                del self.sent_packets[packet_id]
                del self.segment_state[packet_id]

            self.cwnd_available.put(True)
