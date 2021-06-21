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
        self.recv_buffer_stats = []
        self.recv_wnd = 0
        self.last_acknowledged = 0
        self.out = None

    def packet_arrived(self, packet):
        """
        Insert the packet into the receive buffer, which is a priority queue
        that is sorted based on the sequence number of the packet (packet_id).
        """
        self.recv_buffer.put((packet.packet_id, packet))
        self.recv_buffer_stats.append(
            [packet.packet_id, packet.packet_id + packet.size])

        self.recv_buffer_stats.sort(reverse=True)
        merged_stats = []
        for start, end in self.recv_buffer_stats:
            if merged_stats and start <= merged_stats[-1][1]:
                merged_stats[-1][1] = max(merged_stats[-1][1], end)
            else:
                merged_stats.append([start, end])
        self.recv_buffer_stats = merged_stats

    def put(self, packet):
        """ Sends a packet to this element. """
        super().put(packet)

        self.packet_arrived(packet)

        if len(self.recv_buffer_stats) == 1:
            # in-order delivery
            self.last_acknowledged = packet.packet_id + packet.size
        else:
            # out-of-order delivery or retransmissions: needs
            # to go through the receive buffer and find out
            # what the last in-order packet's sequence number is
            self.last_acknowledged = self.recv_buffer_stats[0][1]

        # a TCP sink needs to send ack packets back to the TCP packet generator
        assert self.out is not None

        acknowledgment = Packet(
            self.env.now,
            size=40,  # default size of the ack packet
            packet_id=0,
            flow_id=packet.flow_id + 10000)

        acknowledgment.recv_wnd = self.recv_wnd
        acknowledgment.ack = self.last_acknowledged

        self.out.put(acknowledgment)
