"""
A demultiplexing element that splits packet streams by flow_id.
"""


class FlowDemux:
    """ 
    The constructor takes a list of downstream components for the
    corresponding output ports as its input.
    """
    def __init__(self, outs=None, default=None):
        self.outs = outs
        self.default = default
        self.packets_rec = 0

    def put(self, pkt):
        """ Sends the packet 'pkt' to the next-hop element. """
        self.packets_rec += 1
        flow_id = pkt.flow_id
        if flow_id < len(self.outs):
            self.outs[flow_id].put(pkt)
        else:
            if self.default:
                self.default.put(pkt)
