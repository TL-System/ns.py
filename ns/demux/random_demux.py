"""
A demultiplexing element that chooses the output port at random.
"""

from collections.abc import Sequence
from math import isfinite
from random import choices
from typing import Any

import simpy

from ns.packet.packet import Packet


class RandomDemux:
    """
    The constructor takes a list of output ports and a list of probabilities.
    Use the output ports to connect to other network elements.

    Parameters
    ----------
    env : simpy.Environment
        the simulation environment
    probs : List
        nonnegative, finite relative probability weights for the output ports;
        at least one weight must be positive. They need not sum to one.
    """

    def __init__(self, env: simpy.Environment, probs: Sequence[float]) -> None:
        self.env = env

        self.probs = list(probs)
        if (
            not self.probs
            or any(not isfinite(weight) or weight < 0 for weight in self.probs)
            or not isfinite(sum(self.probs))
            or sum(self.probs) <= 0
        ):
            raise ValueError(
                "Probability weights must be finite, nonnegative, "
                "and have a positive total."
            )
        self.n_ports = len(self.probs)
        self.outs: list[Any] = [None for __ in range(self.n_ports)]
        self.packets_received = 0
        self.packets_dropped = 0

    def put(self, packet: Packet) -> None:
        """Sends a packet to this element."""
        self.packets_received += 1
        out = choices(self.outs, weights=self.probs)[0]
        # A disconnected selected branch drops, rather than changing the draw
        # by retrying until a connected branch happens to win.
        if out is None:
            self.packets_dropped += 1
        else:
            out.put(packet)
