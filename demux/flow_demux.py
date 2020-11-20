
class FlowDemux:
    """ A demultiplexing element that splits packet streams by flow_id.

    Parameters
    ----------
    outs : List
        A list of downstream components for the corresponding output ports
    """
    def __init__(self, outs=None, default=None):
        self.outs = outs
        self.default = default
        self.packets_rec = 0


    def put(self, pkt):
        self.packets_rec += 1
        flow_id = pkt.flow_id
        if flow_id < len(self.outs):
            self.outs[flow_id].put(pkt)
        else:
            if self.default:
                self.default.put(pkt)
