"""
A demultiplexing element that splits packet streams by flow_id.
"""

from collections.abc import Sequence
from typing import Any

from ns.packet.packet import Packet


class FlowDemux:
    """
    The constructor takes a list of downstream elements for the
    corresponding output ports as its input. Nonnegative integer flow IDs index
    this list; unknown IDs or disconnected outputs use ``default`` when supplied.
    ``packets_dropped`` counts packets with no connected output or default.
    """

    def __init__(
        self, outs: Sequence[Any] | None = None, default: Any = None
    ) -> None:
        self.outs = outs if outs is not None else []
        self.default = default
        self.packets_received = 0
        self.packets_dropped = 0

    def put(self, packet: Packet) -> None:
        """Sends a packet to this element."""
        self.packets_received += 1
        flow_id = packet.flow_id
        # A negative ID is an unknown route, not Python's index from the end.
        out = (
            self.outs[flow_id]
            if isinstance(flow_id, int) and 0 <= flow_id < len(self.outs)
            else None
        )
        if out is None:
            out = self.default
        if out is None:
            self.packets_dropped += 1
        else:
            out.put(packet)
