"""
A demultiplexing element that splits packet streams by flow_id.
"""


class FlowDemux:
    """
    The constructor takes a list of downstream elements for the
    corresponding output ports as its input.
    """
    def __init__(self, outs=None, default=None):
        self.outs = outs
        self.default = default
        self.packets_received = 0

    def put(self, packet):
        """ Sends a packet to this element. """
        self.packets_received += 1
        flow_id = packet.flow_id
        if flow_id < len(self.outs):
            self.outs[flow_id].put(packet)
        else:
            if self.default:
                self.default.put(packet)
