"""The color-blind Two Rate Three Color Marker from RFC 2698, section 3.

https://www.rfc-editor.org/rfc/rfc2698
"""

import math
from typing import Any

import simpy

from ns.packet.packet import Packet


class TrTCM:
    """Meter arrivals without delaying/dropping them; set packet.color.

    ``pir`` and ``cir`` are bits/second, unlike the RFC's bytes/second; ``pbs``
    and ``cbs`` are positive byte capacities. PIR must be at least CIR. Initially
    both buckets are full. Refill is continuous, capped, and measured in seconds.
    Green consumes both buckets, yellow consumes only peak tokens, and red
    consumes neither. Exact fits conform; packets larger than PBS are always red.

    This implements the RFC's color-blind mode: an existing color is overwritten
    and flow_id is preserved. A marker describes arrival traffic; a shaper waits
    for tokens and therefore has a different timing contract.
    """

    def __init__(
        self, env: simpy.Environment, pir: float, pbs: float,
        cir: float, cbs: float,
    ) -> None:
        if (
            not all(math.isfinite(value) for value in (pir, pbs, cir, cbs))
            or not 0 <= cir <= pir
            or pbs <= 0
            or cbs <= 0
        ):
            raise ValueError("Require finite PIR >= CIR >= 0 and positive PBS/CBS")
        self.env = env
        self.out: Any = None
        self.pir = pir
        self.pbs = pbs
        self.cir = cir
        self.cbs = cbs
        self.peak_bucket = pbs
        self.committed_bucket = cbs
        self.last_time = env.now

    def put(self, packet: Packet) -> None:
        """Refill and color immediately; this element introduces no SimPy wait."""
        elapsed = self.env.now - self.last_time
        self.last_time = self.env.now
        # Rate is bits/s, so divide by 8 to refill byte-denominated buckets.
        self.peak_bucket = min(self.pbs, self.peak_bucket + self.pir * elapsed / 8)
        self.committed_bucket = min(
            self.cbs, self.committed_bucket + self.cir * elapsed / 8
        )
        if packet.size > self.peak_bucket:
            packet.color = "red"
        elif packet.size > self.committed_bucket:
            packet.color = "yellow"
            self.peak_bucket -= packet.size
        else:
            packet.color = "green"
            self.peak_bucket -= packet.size
            self.committed_bucket -= packet.size
        self.out.put(packet)
