"""
Implements a packet generator that simulates the TCP protocol, including basic flow control
with advertised receive window sizes, as well as various congestion control mechanisms.
"""
from ns.packet.packet import Packet


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
        self.action = env.process(self.run())
        self.flow = flow
        self.seq = 0

        self.mss = 536  # maximum segment size, in bytes
        self.cwnd = self.mss  # the window size

        self.rec_flow = rec_flow
        self.time_rec = []
        self.size_rec = []

        self.debug = debug

    def run(self):
        """The generator function used in simulations."""
        yield self.env.timeout(self.flow.start_time)

        while self.env.now < self.flow.finish_time:
            # wait for the next data arrival
            if self.flow.arrival_dist is not None:
                yield self.env.timeout(self.flow.arrival_dist())

            self.packets_sent += 1
            packet = Packet(self.env.now,
                            self.mss,
                            self.seq,
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

    def put(self, packet):
        """ On receiving an acknowledgment packet. """
        assert packet.ack > 0  # the packet must be an acknowledgment
