"""
Implements a TCPSink, designed to send ack packets back to the TCPPacketGenerator.
"""
from ns.packet.sink import PacketSink
from ns.packet.packet import Packet


class TCPSink(PacketSink):
    """ A TCPSink inherits from the basic PacketSink, and sends ack packets back to the
    TCPPacketGenerator with advertised receive window sizes.
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
        self.recv_buffer = []
        # the next sequence number expected to be received
        self.next_seq_expected = 0
        self.out = None

    def packet_arrived(self, packet):
        """
        Insert the packet into the receive buffer, which is a priority queue
        that is sorted based on the sequence number of the packet (packet_id).
        """
        self.recv_buffer.append(
            [packet.packet_id, packet.packet_id + packet.size])

        self.recv_buffer.sort()

        merged_stats = []
        for start, end in self.recv_buffer:
            if merged_stats and start <= merged_stats[-1][1]:
                merged_stats[-1][1] = max(merged_stats[-1][1], end)
            else:
                merged_stats.append([start, end])
        self.recv_buffer = merged_stats

    def put(self, packet):
        """ Sends a packet to this element. """
        super().put(packet)

        self.packet_arrived(packet)

        if len(self.recv_buffer) == 1:
            # in-order delivery: all data up to but not including
            # `next_seq_expected' have been received
            self.next_seq_expected = packet.packet_id + packet.size
        else:
            # out-of-order delivery or retransmissions: needs
            # to go through the receive buffer and find out
            # what the last in-order packet's sequence number is
            self.next_seq_expected = self.recv_buffer[0][1]

        # a TCP sink needs to send ack packets back to the TCP packet generator
        assert self.out is not None

        acknowledgment = Packet(
            packet.time,  # used for calculating RTT at the sender
            size=40,  # default size of the ack packet
            packet_id=packet.packet_id,
            flow_id=packet.flow_id + 10000)

        acknowledgment.ack = self.next_seq_expected

        self.out.put(acknowledgment)
