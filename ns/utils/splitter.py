"""
Implemented variants of a packet splitter element, which sends a copy of
the arriving packets to each downstream element.
"""
import copy


class Splitter:
    """A simple two-way splitter with two downstream elements."""
    def __init__(self) -> None:
        self.out1 = None
        self.out2 = None

    def put(self, pkt):
        if self.out1:
            self.out1.put(pkt)

        if self.out2:
            self.out2.put(copy.copy(pkt))


class NWaySplitter:
    """An N-way splitter with *N* downstream elements."""
    def __init__(self, N) -> None:
        if isinstance(N, int):
            if N > 1:
                self.outs = [None] * N
                self.N = N
            else:
                raise ValueError("N should be larger than 1.")
        else:
            raise TypeError("N should be an integer larger than 1.")

    def put(self, pkt):
        """ Sends the packet 'pkt' to this element. """
        self.outs[0].put(pkt)

        for i in range(self.N - 1):
            pkt_copy = copy.copy(pkt)
            self.outs[i + 1].put(pkt_copy)
