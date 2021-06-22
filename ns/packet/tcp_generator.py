"""
Implements a packet generator that simulates the TCP protocol, including basic flow control
with advertised receive window sizes, as well as various congestion control mechanisms.
"""
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
                 element_id=None,
                 rec_flow=False,
                 debug=False):
        self.element_id = element_id
        self.env = env
        self.out = None
        self.packets_sent = 0
        self.flow = flow
        self.bytes_acked = 0

        self.mss = 536  # maximum segment size, in bytes

        # the next sequence number to be sent, in bytes
        self.next_seq = 0
        # the maximum sequence number in the 'in-flight' data buffer
        self.send_buffer = 0
        # the size of the congestion window
        self.cwnd = self.mss
        # the sequence number of the packet that is last acknowledged
        self.last_ack = 0
        # the timers, one for each segment sent
        self.timers = {}
        # the count of duplicate acknolwedgments
        self.dupack = 0
        # the timeout value
        self.timeout = 1

        self.rec_flow = rec_flow
        self.time_rec = []
        self.size_rec = []

        self.action = env.process(self.run())
        self.debug = debug

    def run(self):
        """The generator function used in simulations."""
        yield self.env.timeout(self.flow.start_time)

        while self.env.now < self.flow.finish_time and self.bytes_acked <= self.flow.size:
            # wait for the next data arrival
            if self.flow.arrival_dist is not None:
                yield self.env.timeout(self.flow.arrival_dist())
            if self.flow.size_dist is not None:
                self.send_buffer += self.flow.size_dist()
            else:
                self.send_buffer += self.mss

            if self.last_ack + self.cwnd >= self.next_seq + self.mss:
                self.packets_sent += 1

                packet = Packet(self.env.now,
                                self.mss,
                                self.next_seq,
                                src=self.element_id,
                                flow_id=self.flow.fid)

                if self.rec_flow:
                    self.time_rec.append(packet.time)
                    self.size_rec.append(packet.size)

                if self.debug:
                    print(
                        f"Sent packet {packet.packet_id} with flow_id {packet.flow_id} at "
                        f"time {self.env.now}.")

                self.out.put(packet)

                self.next_seq += packet.size
                self.timers[packet.packet_id] = Timer(self.env,
                                                      packet.packet_id,
                                                      self.timer_expired,
                                                      self.timeout)

    def timer_expired(self, packet_id):
        print(f"Timer expired for packet #{packet_id}.")

    def put(self, packet):
        """ On receiving an acknowledgment packet. """
        assert packet.flow_id > 10000  # the received packet must be an ack

        if packet.flow_id == self.last_ack:
            self.dupack += 1
        else:
            self.dupack = 0

        if self.dupack >= 3:
            # fast retransmit
            return
