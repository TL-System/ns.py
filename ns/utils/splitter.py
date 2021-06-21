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

    def put(self, packet):
        """ Sends a packet to this element. """
        if self.out1:
            self.out1.put(packet)

        if self.out2:
            self.out2.put(copy.copy(packet))


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

    def put(self, packet):
        """ Sends a packet to this element. """
        self.outs[0].put(packet)

        for i in range(self.N - 1):
            packet_copy = copy.copy(packet)
            self.outs[i + 1].put(packet_copy)
