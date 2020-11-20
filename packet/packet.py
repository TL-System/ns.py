"""
A very simple class that represents a packet.
"""
class Packet:
    """
        This packet is generally created by PacketGenerators, and will run through
        a queue at a switch output port.

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
        id: int
            an identifier for the packet
        src, dst: int
            identifiers for source and destination
        flow_id: int
            small integer that can be used to identify a flow
    """
    def __init__(self, time, size, packet_id, src="a", dst="z", flow_id=0):
        self.time = time
        self.size = size
        self.id = packet_id
        self.src = src
        self.dst = dst
        self.flow_id = flow_id


    def __repr__(self):
        return "id: {}, src: {}, time: {}, size: {}".\
            format(self.id, self.src, self.time, self.size)
