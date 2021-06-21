"""
Implements a TCPSink, designed to send ack packets back to the TCPPacketGenerator.
"""
from queue import PriorityQueue

from ns.packet.sink import PacketSink
from ns.packet.packet import Packet


class TCPSink(PacketSink):
    """ A TCPSink inherits from the basic PacketSink, and sends ack packets back to the
    TCPPacketGenerator with advertised receive window sizes.

    Parameters
    ----------
    env: simpy.Environment
        the simulation environment
    rec_arrivals: bool
        if True, arrivals will be recorded
    absolute_arrivals: bool
        if True absolute arrival times will be recorded, otherwise the time between
        consecutive arrivals is recorded.
    rec_waits: bool
        if True, the waiting times experienced by the packets are recorded
    rec_flow_ids: bool
        if True, the flow IDs that the packets are used as the index for recording;
        otherwise, the 'src' field in the packets are used
    ack:
        if this is not None, the same packet will be sent back to this element as
        an acknowledgement, with a constant size of 32 and a new flow_id of 1000 +
        this packet's flow_id.
    debug: bool
        If True, prints more verbose debug information.
    """
    def __init__(self,
                 env,
                 rec_arrivals: bool = True,
                 absolute_arrivals: bool = True,
                 rec_waits: bool = True,
                 rec_flow_ids: bool = True,
                 debug: bool = False):
        super().__init__(env, rec_arrivals, absolute_arrivals, rec_waits,
                         rec_flow_ids, debug)
        self.recv_buffer = PriorityQueue()
        self.recv_wnd = 0
        self.last_received = 0
        self.out = None

    def put(self, packet):
        """ Sends a packet to this element. """
        super().put(packet)
        self.recv_buffer.put(packet)

        if packet.seq - self.last_received == packet.size:
            # in-order delivery
            self.last_received = packet.seq
        else:
            # out-of-order delivery or retransmissions, needs
            # to go through the receive buffer and find out
            # what the last in-order packet's seq number is
            self.last_received = packet.seq

        if self.out:
            acknowledgment = Packet(
                self.env.now,
                size=40,  # default size of the ack packet
                packet_id=self.last_received,
                flow_id=packet.flow_id + 10000)

            acknowledgment.recv_wnd = self.recv_wnd
            acknowledgment.ack = self.last_received

            self.out.put(acknowledgment)
