"""
Implements a TCPSink, designed to send ack packets back to the
TCPPacketGenerator.
"""

from ns.packet.sink import PacketSink
from ns.packet.packet import Packet


class TCPSink(PacketSink):
    """Receive one TCP connection and immediately acknowledge contiguous bytes.

    Data sequences start at byte zero. Overlaps and duplicate attempts share a
    single receive range, so they cannot deliver application bytes twice.
    Inherited PacketSink counters and delay samples still describe physical
    arrivals, including retransmissions; ``bytes_delivered`` counts the unique
    contiguous application prefix. No receive-window or delayed-ACK model is used.
    """

    def __init__(
        self,
        env,
        rec_arrivals: bool = True,
        absolute_arrivals: bool = True,
        rec_waits: bool = True,
        rec_flow_ids: bool = True,
        debug: bool = False,
        element_id: int = 0,
    ):
        super().__init__(
            env, rec_arrivals, absolute_arrivals, rec_waits, rec_flow_ids, debug
        )
        self.recv_buffer = []
        # RCV.NXT is the first missing byte, also the application-delivery frontier.
        self.next_seq_expected = 0
        self.out = None
        self.ele_id = element_id

    @property
    def bytes_delivered(self):
        """Unique in-order application bytes; buffered data beyond a gap waits."""
        return self.next_seq_expected

    def packet_arrived(self, packet):
        """Merge this byte interval with sorted overlapping or adjacent ranges."""

        self.recv_buffer.append([packet.packet_id, packet.packet_id + packet.size])

        self.recv_buffer.sort()

        merged_stats = []
        for start, end in self.recv_buffer:
            if merged_stats and start <= merged_stats[-1][1]:
                merged_stats[-1][1] = max(merged_stats[-1][1], end)
            else:
                merged_stats.append([start, end])
        self.recv_buffer = merged_stats

    def put(self, packet):
        """Sends a packet to this element."""
        super().put(packet)

        self.packet_arrived(packet)
        # Only a range touching the current frontier can close its next gap.
        # Retaining the merged [0, frontier) prefix also absorbs late duplicates.
        frontier = self.next_seq_expected
        for start, end in self.recv_buffer:
            if start > frontier:
                break
            frontier = max(frontier, end)
        self.next_seq_expected = frontier

        # a TCP sink needs to send ack packets back to the TCP packet generator
        assert self.out is not None

        acknowledgment = Packet(
            # Echo the original latency timestamp for compatibility. RTT/RTO
            # timing comes from sender-owned segment state, never this echo.
            packet.time,
            size=40,  # default size of the ack packet
            packet_id=packet.packet_id,
            flow_id=packet.flow_id + 10000,
        )

        acknowledgment.ack = self.next_seq_expected
        # BBR uses these echoed fields for its separate delivery-rate sampler.
        acknowledgment.delivered_time = packet.delivered_time
        acknowledgment.first_sent_time = packet.first_sent_time
        acknowledgment.delivered = packet.delivered
        acknowledgment.lost = packet.lost
        acknowledgment.is_app_limited = packet.is_app_limited

        self.out.put(acknowledgment)
