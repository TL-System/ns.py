class FIBDemux:
    """
    The constructor takes a list of downstream elements for the
    corresponding output ports as its input. Terminal deliveries in ``ends``
    take precedence over routes. Unknown routes, invalid port indexes, and
    disconnected outputs use ``default``; otherwise they count as a drop.

    Parameters
    ----------
    fib: dict
        forwarding information base. Key: flow id, Value: output port
    outs: list
        list of downstream elements corresponding to the output ports
    ends: dict
        terminal downstream elements keyed by flow ID
    default:
        default downstream element
    """

    def __init__(
        self, fib: dict = None, outs: list = None, ends: dict = None, default=None
    ) -> None:
        self.outs = outs if outs is not None else []
        self.default = default
        self.packets_received = 0
        self.packets_dropped = 0
        self.fib = fib if fib is not None else {}
        self.ends = ends if ends is not None else {}

    def put(self, packet):
        """Sends a packet to this element."""
        self.packets_received += 1
        flow_id = packet.flow_id

        if flow_id in self.ends:
            out = self.ends[flow_id]
        else:
            port = self.fib.get(flow_id)
            out = (
                self.outs[port]
                if isinstance(port, int) and 0 <= port < len(self.outs)
                else None
            )
        if out is None:
            out = self.default
        if out is None:
            self.packets_dropped += 1
        else:
            # Only routing failures use the default. An exception raised by a
            # downstream element must propagate, without sending the packet twice.
            out.put(packet)
