"""
Implemented a tagged and ordered variant of the simpy.Store class.
The `tag` is used to sort the elements for removal ordering. This is
useful in the implementation of more sophisticated queueing disciplines,
such as Weighted Fair Queueing and Virtual Clock.
"""

from heapq import heappop, heappush

from simpy.core import BoundClass
from simpy.resources import base


class TaggedStorePut(base.Put):
    """Put `item` into the store if possible, or wait until it is.
    The item must be a tuple (tag, contents) where the tag is used
    to sort the content in the TaggedStore.
    """

    def __init__(self, resource, item):
        # The item to be put into the store.
        self.item = item
        super().__init__(resource)


class TaggedStoreGet(base.Get):
    """Get an item from the store or wait until one is available."""


class TaggedStore(base.BaseResource):
    """Models the production and consumption of concrete Python objects.

    Put items are ``(tag, contents)`` pairs. Get returns only the contents,
    selecting the lowest tag first and retaining put order among equal tags.
    Contents need not be comparable: the insertion counter breaks heap ties.

    The `env` parameter is an instance of the `simpy.core.Environment` class.

    The `capacity` parameter defines the size of the Store and must be a positive
    number (> 0). By default, a Store is of unlimited size. A `ValueError` exception
    is raised if capacity is nonpositive or NaN. A full store leaves puts pending
    in SimPy's FIFO put queue until a get frees capacity.
    """

    def __init__(self, env, capacity=float("inf")):
        super().__init__(env, capacity=float("inf"))

        if not capacity > 0:
            raise ValueError('"capacity" must be > 0.')

        self._capacity = capacity
        self.items = []  # we are keeping items sorted by their tags
        self.event_count = 0  # Used to break ties with python heap implementation

    @property
    def capacity(self):
        """The maximum capacity of the tagged store."""
        return self._capacity

    put = BoundClass(TaggedStorePut)
    """Create a new `StorePut` event."""

    get = BoundClass(TaggedStoreGet)
    """Create a new `StoreGet` event."""

    # We assume the item is a tuple: (tag, packet). The tag is used to
    # sort the packet in the heap.
    def _do_put(self, event):
        if len(self.items) < self._capacity:
            self.event_count += 1  # Count admissions, not retries of pending puts.
            heappush(self.items, [event.item[0], self.event_count, event.item[1]])
            event.succeed()

    # When we return an item from the tagged store we do not need to
    # return the tag, only the content of the item.
    def _do_get(self, event):
        if self.items:
            event.succeed(heappop(self.items)[2])
