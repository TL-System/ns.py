"""
Implemented a tagged and ordered variant of the simpy.Store class.
The `tag` is used to sort the elements for removal ordering. This is
useful in the implementation of more sophisticated queueing disciplines,
such as Weighted Fair Queueing and Virtual Clock.
"""

from __future__ import annotations

from collections.abc import Callable
from heapq import heapify, heappop, heappush
from typing import Any, Protocol, cast

import simpy
from simpy.core import BoundClass
from simpy.resources import base


class TaggedStorePut(base.Put):
    """Put `item` into the store if possible, or wait until it is.
    The item must be a tuple (tag, contents) where the tag is used
    to sort the content in the TaggedStore.
    """

    def __init__(self, resource: TaggedStore, item: tuple[float, object]) -> None:
        # The item to be put into the store.
        self.item = item
        super().__init__(resource)


class TaggedStoreGet(base.Get):
    """Get the smallest tag, or a requested object by identity; wait if absent."""

    def __init__(self, resource: TaggedStore, item: object | None = None) -> None:
        self.item = item
        super().__init__(resource)


class _BoundGet(Protocol):
    def __call__(self, item: object | None = None) -> TaggedStoreGet: ...


class TaggedStore(base.BaseResource[TaggedStorePut, TaggedStoreGet]):
    """Models the production and consumption of concrete Python objects.

    Put items are ``(tag, contents)`` pairs. Get returns only the contents,
    selecting the lowest tag first and retaining put order among equal tags.
    Contents need not be comparable: the insertion counter breaks heap ties.
    ``get(item)`` instead removes that exact object, for downstream release of
    retained packets that may have been reordered by a different scheduler.
    ``get()`` (or ``get(None)``) retains the usual smallest-tag selection.

    The `env` parameter is an instance of the `simpy.core.Environment` class.

    The `capacity` parameter defines the size of the Store and must be a positive
    number (> 0). By default, a Store is of unlimited size. A `ValueError` exception
    is raised if capacity is nonpositive or NaN. A full store leaves puts pending
    in SimPy's FIFO put queue until a get frees capacity.
    """

    def __init__(self, env: simpy.Environment, capacity: float = float("inf")) -> None:
        super().__init__(env, capacity=float("inf"))

        if not capacity > 0:
            raise ValueError('"capacity" must be > 0.')

        self._capacity = capacity
        self.items: list[list[Any]] = []  # Tag, tie-break counter, and opaque item.
        self.event_count = 0  # Used to break ties with python heap implementation

    @property
    def capacity(self) -> float:
        """The maximum capacity of the tagged store."""
        return self._capacity

    # SimPy binds these descriptors to the store instance. State their bound
    # signatures so callers see normal event-producing methods.
    put = cast(Callable[[tuple[float, object]], TaggedStorePut], BoundClass(TaggedStorePut))
    """Create a new `StorePut` event."""

    get = cast(_BoundGet, BoundClass(TaggedStoreGet))
    """Create a new `StoreGet` event."""

    # We assume the item is a tuple: (tag, packet). The tag is used to
    # sort the packet in the heap.
    def _do_put(self, event: TaggedStorePut) -> None:
        if len(self.items) < self._capacity:
            self.event_count += 1  # Count admissions, not retries of pending puts.
            heappush(self.items, [event.item[0], self.event_count, event.item[1]])
            event.succeed()

    # When we return an item from the tagged store we do not need to
    # return the tag, only the content of the item.
    def _do_get(self, event: TaggedStoreGet) -> bool | None:
        if event.item is None and self.items:
            event.succeed(heappop(self.items)[2])
        elif event.item is not None:
            for index, entry in enumerate(self.items):
                if entry[2] is event.item:
                    self.items.pop(index)
                    # An arbitrary removal must restore the heap, retaining
                    # every other packet's original tag and admission counter.
                    heapify(self.items)
                    event.succeed(entry[2])
                    break
            # A missing identity does not reserve other queued objects: later
            # ordinary or identity-specific gets may still consume those.
            return True
