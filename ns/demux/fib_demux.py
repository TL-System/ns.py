class FIBDemux:
    """
    The constructor takes a litst of downstream components for the
    corresponding output ports as its input

    Parameters
    ----------
    env: simpy.Environment
    fib: Dictionary
        forwarding information base. Key: flow id, Value: output port
    outs: List
        list of output ports
    default: simpy.Process
        default output port
    """
    def __init__(self,
                 env,
                 fib=None,
                 outs=None,
                 ends=None,
                 default=None) -> None:
        self.outs = outs
        self.default = default
        self.packets_received = 0
        self.fib = fib
        if ends:
            self.ends = ends
        else:
            self.ends = dict()

    def put(self, pkt):
        """ Sends the packet 'pkt' to this element. """
        self.packets_received += 1
        flow_id = pkt.flow_id
        if flow_id in self.ends:
            self.ends[flow_id].put(pkt)
        else:
            try:
                self.outs[self.fib[pkt.flow_id]].put(pkt)
            except (KeyError, IndexError, ValueError) as e:
                print("FIB Demux Error" + str(e))
                if self.default:
                    self.default.put(pkt)
