from simpy.resources import base
from simpy.core import BoundClass
from heapq import heappush, heappop

"""
    Trying to implement a stamped/ordered version of the Simpy Store class.
    The "stamp" is used to sort the elements for removal ordering. This
    can be used in the implementation of sophisticated queueing disciplines, but
    would be overkill for fixed priority schemes.
"""

class StampedStorePut(base.Put):
    """ Put *item* into the store if possible or wait until it is.
        The item must be a tuple (stamp, contents) where the stamp is used to sort
        the content in the StampedStore.
    """
    def __init__(self, resource, item):
        self.item = item
        """The item to put into the store."""
        super().__init__(resource)


class StampedStoreGet(base.Get):
    """Get an item from the store or wait until one is available."""
    pass


class StampedStore(base.BaseResource):
    """Models the production and consumption of concrete Python objects.

    Items put into the store can be of any type.  By default, they are put and
    retrieved from the store in a first-in first-out order.

    The *env* parameter is the :class:`~simpy.core.Environment` instance the
    container is bound to.

    The *capacity* defines the size of the Store and must be a positive number
    (> 0). By default, a Store is of unlimited size. A `ValueError` exception is
    raised if the value is negative.
    """
    def __init__(self, env, capacity=float('inf')):
        super().__init__(env, capacity=float('inf'))

        if capacity <= 0:
            raise ValueError('"capacity" must be > 0.')

        self._capacity = capacity
        self.items = []  # we are keeping items sorted by stamp
        self.event_count = 0 # Used to break ties with python heap implementation


    @property
    def capacity(self):
        """The maximum capacity of the store."""
        return self._capacity


    put = BoundClass(StampedStorePut)
    """Create a new :class:`StorePut` event."""


    get = BoundClass(StampedStoreGet)
    """Create a new :class:`StoreGet` event."""


    # We assume the item is a tuple: (stamp, packet). The stamp is used to
    # sort the packet in the heap.
    def _do_put(self, event):
        self.event_count += 1 # Needed this to break heap ties
        if len(self.items) < self._capacity:
            heappush(self.items, [event.item[0], self.event_count, event.item[1]])
            event.succeed()


    # When we return an item from the stamped store we do not
    # return the stamp but only the content portion.
    def _do_get(self, event):
        if self.items:
            event.succeed(heappop(self.items)[2])
