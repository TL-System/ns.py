"""Release packet ownership after a downstream scheduler has reordered service."""

from typing import Any

import simpy

from ns.packet.packet import Packet
from ns.utils.taggedstore import TaggedStore


def remove_packet(store: Any, packet: Packet) -> simpy.Event:
    """Remove the exact retained packet while preserving pending-put wakeups.

    Ownership stores do not have pending service gets: a separate downstream
    queue drives local selection. Downstream order may differ from the retained
    FIFO or heap, so an unconditional get would release a different packet.
    Minimal adapters exposing only get() retain that existing callback API.
    """
    if isinstance(store, TaggedStore):
        return store.get(packet)
    if hasattr(store, "items"):
        index = next(i for i, item in enumerate(store.items) if item is packet)
        # Move only the selected object, leaving all remaining FIFO order intact.
        # A real Store.get() schedules the usual SimPy capacity wakeup callbacks.
        store.items.insert(0, store.items.pop(index))
    return store.get()
