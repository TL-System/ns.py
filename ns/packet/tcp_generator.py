"""
Implements a packet generator that simulates the TCP protocol, including support for
various congestion control mechanisms.
"""
import simpy

from ns.packet.packet import Packet
from ns.utils.timer import Timer


class TCPPacketGenerator:
    """ Generates packets with a simulated TCP protocol.

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
    def __init__(self,
                 env,
                 flow,
                 cc,
                 element_id=None,
                 rtt_estimate=1,
                 debug=False):
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
        # the RTT estimate
        self.rtt_estimate = rtt_estimate
        # the retransmission timeout
        self.rto = self.rtt_estimate * 2
        # an estimate of the RTT deviation
        self.est_deviation = 0
        # whether or not space in the congestion window is available
        self.cwnd_available = simpy.Store(env)

        # the timers, one for each in-flight packets (segments) sent
        self.timers = {}
        # the in-flight packets (segments)
        self.sent_packets = {}

        self.action = env.process(self.run())
        self.debug = debug

    def run(self):
        """ The generator function used in simulations. """
        if self.flow.start_time:
            yield self.env.timeout(self.flow.start_time)

        while self.env.now < self.flow.finish_time:
            if self.flow.size is not None and self.next_seq >= self.flow.size:
                return

            while self.next_seq >= self.send_buffer:
                # retrieving more packets from the (application-layer) flow
                if self.flow.arrival_dist is not None:
                    # if the flow has an arrival distribution, wait for the next arrival
                    wait_time = self.flow.arrival_dist() - (self.env.now -
                                                            self.last_arrival)
                    if wait_time > 0:
                        yield self.env.timeout(wait_time)
                    self.last_arrival = self.env.now

                packet_size = 0
                if self.flow.size_dist is not None:
                    packet_size = self.flow.size_dist()
                else:
                    if self.flow.size is not None:
                        packet_size = min(self.mss,
                                          self.flow.size - self.next_seq)
                    else:
                        packet_size = self.mss
                self.send_buffer += packet_size

            # the sender can transmit up to the size of the congestion window
            if self.next_seq + self.mss <= min(
                    self.send_buffer,
                    self.last_ack + self.congestion_control.cwnd):
                packet = Packet(self.env.now,
                                self.mss,
                                self.next_seq,
                                src=self.flow.src,
                                flow_id=self.flow.fid)

                self.sent_packets[packet.packet_id] = packet

                if self.debug:
                    print("Sent packet {:d} with size {:d}, "
                          "flow_id {:d} at time {:.4f}.".format(
                              packet.packet_id, packet.size, packet.flow_id,
                              self.env.now))

                self.out.put(packet)

                self.next_seq += packet.size
                self.timers[packet.packet_id] = Timer(
                    self.env,
                    timer_id=packet.packet_id,
                    timeout_callback=self.timeout_callback,
                    timeout=self.rto)

                if self.debug:
                    print("Setting a timer for packet {:d} with an RTO"
                          " of {:.4f}.".format(packet.packet_id, self.rto))
            else:
                # No further space in the congestion window to transmit packets
                # at this time, waiting for acknowledgements
                yield self.cwnd_available.get()

    def timeout_callback(self, packet_id):
        """ To be called when a timer expired for a packet with 'packet_id'. """
        if self.debug:
            print("Timer expired for packet {:d} at time {:.4f}.".format(
                packet_id, self.env.now))

        self.congestion_control.timer_expired()

        # retransmitting the segment
        resent_pkt = self.sent_packets[packet_id]
        self.out.put(resent_pkt)

        if self.debug:
            print("Resending packet {:d} with flow_id {:d} at time {:.4f}.".
                  format(resent_pkt.packet_id, resent_pkt.flow_id,
                         self.env.now))

        # starting a new timer for this segment and doubling the retransmission timeout
        self.rto *= 2
        self.timers[packet_id].restart(self.rto)

    def put(self, ack):
        """ On receiving an acknowledgment packet. """
        assert ack.flow_id >= 10000  # the received packet must be an ack

        if ack.ack == self.last_ack:
            self.dupack += 1
        else:
            # fast recovery in RFC 2001 and TCP Reno
            if self.dupack > 0:
                self.congestion_control.dupack_over()
                self.dupack = 0

        if self.dupack == 3:
            self.congestion_control.consecutive_dupacks_received()

            resent_pkt = self.sent_packets[ack.ack]
            resent_pkt.time = self.env.now
            if self.debug:
                print(
                    "Resending packet {:d} with flow_id {:d} at time {:.4f}.".
                    format(resent_pkt.packet_id, resent_pkt.flow_id,
                           self.env.now))

            self.out.put(resent_pkt)

            return
        elif self.dupack > 3:
            self.congestion_control.more_dupacks_received()

            if self.last_ack + self.congestion_control.cwnd >= ack.ack:
                resent_pkt = self.sent_packets[ack.ack]
                resent_pkt.time = self.env.now

                if self.debug:
                    print(
                        "Resending packet {:d} with flow_id {:d} at time {:.4f}."
                        .format(resent_pkt.packet_id, resent_pkt.flow_id,
                                self.env.now))

                self.out.put(resent_pkt)

            return

        if self.dupack == 0:
            # new ack received, update the RTT estimate and the retransmission timout
            sample_rtt = self.env.now - ack.time

            # Jacobsen '88: Congestion Avoidance and Control
            sample_err = sample_rtt - self.rtt_estimate
            self.rtt_estimate += 0.125 * sample_err
            self.est_deviation += 0.25 * (abs(sample_err) - self.est_deviation)
            self.rto = self.rtt_estimate + 4 * self.est_deviation

            self.last_ack = ack.ack
            self.congestion_control.ack_received(sample_rtt, self.env.now)

            if self.debug:
                print("Ack received till sequence number {:d} at time {:.4f}.".
                      format(ack.ack, self.env.now))
                print(
                    "Congestion window size = {:.1f}, last ack = {:d}.".format(
                        self.congestion_control.cwnd, self.last_ack))

            if ack.packet_id in self.timers:
                self.timers[ack.packet_id].stop()
                del self.timers[ack.packet_id]
                del self.sent_packets[ack.packet_id]

            self.cwnd_available.put(True)
