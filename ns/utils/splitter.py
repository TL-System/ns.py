"""
Implemented variants of a packet splitter element, which sends a copy of
the arriving packets to each downstream element.
"""

import copy
from typing import Any

from ns.packet.packet import Packet


def _copy_packet(packet: Packet) -> Packet:
    """Copy path-owned metadata while keeping opaque application payload shared."""
    duplicate = copy.copy(packet)
    duplicate.prio = copy.deepcopy(packet.prio)
    duplicate.perhop_time = copy.deepcopy(packet.perhop_time)
    return duplicate


class Splitter:
    """A simple two-way splitter with two downstream elements."""

    def __init__(self) -> None:
        self.out1 = None
        self.out2 = None

    def put(self, packet: Packet) -> None:
        """Sends a packet to this element."""
        # Snapshot before calling any downstream put(): it can synchronously
        # update priorities, per-hop times, or other scalar packet attributes.
        duplicate = _copy_packet(packet) if self.out2 is not None else None
        if self.out1 is not None:
            self.out1.put(packet)

        if self.out2 is not None:
            self.out2.put(duplicate)


class NWaySplitter:
    """An N-way splitter with *N* downstream elements."""

    def __init__(self, N: int) -> None:
        if isinstance(N, int):
            if N > 1:
                self.outs: list[Any] = [None] * N
                self.N = N
            else:
                raise ValueError("N should be larger than 1.")
        else:
            raise TypeError("N should be an integer larger than 1.")

    def put(self, packet: Packet) -> None:
        """Sends a packet to this element."""
        # Every branch starts with the arrival's metadata, even if the first
        # branch mutates its packet inside put(). Disconnected branches are unused.
        packets = [packet] + [_copy_packet(packet) for _ in range(self.N - 1)]
        for out, branch_packet in zip(self.outs, packets):
            if out is not None:
                out.put(branch_packet)
