"""
A very simple class that represents a packet.
"""


class Packet:
    """
        Packets in ns.py are generally created by packet generators, and will run through
        a queue at an output port.

        Key fields include: generation time, size, flow_id, packet id, source, and
        destination. We do not model upper layer protocols, i.e., packets don't contain
        a payload. The size (in bytes) field is used to determine its transmission time.

        We use a float to represent the size of the packet in bytes so that we can compare
        to ideal M/M/1 queues.

        Parameters
        ----------
        time: float
            the time when the packet is generated.
        size: float
            the size of the packet in bytes
        packet_id: int
            an identifier for the packet
        src, dst: int
            identifiers for the source and destination
        flow_id: int or str
            an integer or string that can be used to identify a flow
    """
    def __init__(self,
                 time,
                 size,
                 packet_id,
                 src="source",
                 dst="destination",
                 flow_id=0):
        self.time = time
        self.size = size
        self.packet_id = packet_id
        self.src = src
        self.dst = dst
        self.flow_id = flow_id

        self.color = None  # Used by the two-rate tri-color token bucket shaper
        self.prio = 0  # used by the Static Priority scheduler
        self.ack = 0  # used by TCPPacketGenerator and TCPSink
        self.current_time = 0  # used by the Wire element
        self.perhop_time = {}  # used by Port to record per-hop arrival times

    def __repr__(self):
        return f"id: {self.packet_id}, src: {self.src}, time: {self.time}, size: {self.size}"
