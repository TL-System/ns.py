class FIBDemux:
    """
    The constructor takes a list of downstream elements for the
    corresponding output ports as its input.

    Parameters
    ----------
    fib: dict
        forwarding information base. Key: flow id, Value: output port
    outs: list
        list of downstream elements corresponding to the output ports
    ends: list
        list of downstream elements corresponding to the output ports
    default:
        default downstream element
    """
    def __init__(self,
                 fib: dict = None,
                 outs: list = None,
                 ends: dict = None,
                 default=None) -> None:
        self.outs = outs
        self.default = default
        self.packets_received = 0
        self.fib = fib
        if ends:
            self.ends = ends
        else:
            self.ends = dict()

    def put(self, packet):
        """ Sends a packet to this element. """
        self.packets_received += 1
        flow_id = packet.flow_id

        if flow_id in self.ends:
            self.ends[flow_id].put(packet)
        else:
            try:
                self.outs[self.fib[packet.flow_id]].put(packet)
            except (KeyError, IndexError, ValueError) as exc:
                print("FIB Demux Error: " + str(exc))
                if self.default:
                    self.default.put(packet)
