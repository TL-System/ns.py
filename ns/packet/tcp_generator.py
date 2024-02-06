"""
Implements a packet generator that simulates the TCP protocol, including support for
various congestion control mechanisms.
"""

import simpy

from ns.packet.packet import Packet
from ns.utils.timer import Timer


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
        # whether or not space in the congestion window is available
        self.cwnd_available = simpy.Store(env)

        # the timers, one for each in-flight packets (segments) sent
        self.timers = {}
        # the in-flight packets (segments)
        self.sent_packets = {}

        self.action = env.process(self.run())
        self.debug = debug

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

            # the sender can transmit up to the size of the congestion window
            if self.next_seq + self.mss <= min(
                self.send_buffer, self.last_ack + self.congestion_control.cwnd
            ):
                packet = Packet(
                    self.env.now,
                    self.mss,
                    self.next_seq,
                    src=self.flow.src,
                    flow_id=self.flow.fid,
                )

                self.sent_packets[packet.packet_id] = packet

                if self.debug:
                    print(
                        f"TCPPacketGenerator {self.element_id} sent packet {packet.packet_id} "
                        f"with size {packet.size}, flow_id {packet.flow_id} at "
                        f"time {self.env.now:.4f}."
                    )

                self.out.put(packet)

                self.next_seq += packet.size
                self.timers[packet.packet_id] = Timer(
                    self.env,
                    timer_id=packet.packet_id,
                    timeout_callback=self.timeout_callback,
                    timeout=self.rto,
                )

                if self.debug:
                    print(
                        f"TCPPacketGenerator {self.element_id} is setting a timer "
                        f"for packet {packet.packet_id} with an RTO of {self.rto:.4f}."
                    )
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
        resent_pkt = self.sent_packets[packet_id]
        self.out.put(resent_pkt)

        if self.debug:
            print(
                f"TCPPacketGenerator {self.element_id} is resending packet {resent_pkt.packet_id} "
                f"with flow_id {resent_pkt.flow_id} at time {self.env.now:.4f}."
            )

        # starting a new timer for this segment and doubling the retransmission timeout
        self.rto *= 2
        self.timers[packet_id].restart(self.rto)

    def put(self, ack):
        """On receiving an acknowledgment packet."""
        assert ack.flow_id >= 10000  # the received packet must be an ack

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

            resent_pkt = self.sent_packets[ack.ack]
            resent_pkt.time = self.env.now
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
                    packet = Packet(
                        self.env.now,
                        self.mss,
                        self.next_seq,
                        src=self.flow.src,
                        flow_id=self.flow.fid,
                    )

                    self.sent_packets[packet.packet_id] = packet

                    if self.debug:
                        print(
                            f"TCPPacketGenerator {self.element_id} sent packet "
                            f"{packet.packet_id} with size {packet.size}, flow_id "
                            f"{packet.flow_id} at time {self.env.now:.4f} as dupack > 3."
                        )

                    self.out.put(packet)

                    self.next_seq += packet.size
                    self.timers[packet.packet_id] = Timer(
                        self.env,
                        timer_id=packet.packet_id,
                        timeout_callback=self.timeout_callback,
                        timeout=self.rto,
                    )

                    if self.debug:
                        print(
                            f"TCPPacketGenerator {self.element_id} is setting a timer for "
                            f"packet {packet.packet_id} with an RTO of {self.rto:.4f}."
                        )

            return

        if self.dupack == 0:
            # new ack received, update the RTT estimate and the retransmission timout
            sample_rtt = self.env.now - ack.time

            # Authoritative sources for RTO calculation

            # RFC 6298: Computing TCP's Retransmission Timer

            # This RFC specifically focuses on the RTO algorithm and updates the
            # way RTO is calculated. It obsoletes the RTO calculation described
            # in RFC 2988. The updated algorithm is commonly referred to as the
            # "Karn/Partridge Algorithm."

            alpha = 0.125
            beta = 0.25

            # calculates the deviation (RTTVAR) of the RTT to account for
            # variations in the network
            if self.rtt_var == 0.0:
                self.rtt_var = sample_rtt / 2.0
            else:
                deviation = self.smoothed_rtt - sample_rtt
                self.rtt_var = (1.0 - beta) * self.rtt_var + beta * abs(deviation)

            # computes a smoothed round-trip time (SRTT)
            if self.smoothed_rtt == 0.0:
                self.smoothed_rtt = sample_rtt
            else:
                self.smoothed_rtt = (
                    1.0 - alpha
                ) * self.smoothed_rtt + alpha * sample_rtt
            self.rto = max(1.0, self.smoothed_rtt + 4.0 * self.rtt_var)

            self.last_ack = ack.ack
            self.congestion_control.ack_received(sample_rtt, self.env.now)

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
            acked_packets = [
                packet_id
                for packet_id, _ in self.sent_packets.items()
                if packet_id < ack.ack
            ]
            for packet_id in acked_packets:
                if self.debug:
                    print(
                        f"TCPPacketGenerator {self.element_id} stopped timer "
                        f"{packet_id} at time {self.env.now:.4f}."
                    )
                self.timers[packet_id].stop()
                del self.timers[packet_id]
                del self.sent_packets[packet_id]

            self.cwnd_available.put(True)
