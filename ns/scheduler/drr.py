"""
Implements a Deficit Round Robin (DRR) server.

Reference:

M. Shreedhar and G. Varghese, "Efficient Fair Queuing Using Deficit Round-Robin,"
IEEE/ACM Trans. Networking, vol. 4, no. 3, June 1996.
"""

from collections import defaultdict as dd
from collections import deque
from collections.abc import Callable, Generator, Hashable
from math import isfinite
from typing import Any

import simpy

from ns.packet.packet import Packet
from ns.utils.retained_store import remove_packet


class DRRServer:
    """
    Parameters
    ----------
    env: simpy.Environment
        The simulation environment.
    rate: float
        The finite, positive bit rate of the port.
    weights: list or dict
        A list indexes finite, positive weights by class ID; a dictionary maps
        class IDs to those weights. With the default classifier, IDs are flow IDs.
    flow_classes: function
        Maps a packet to its class ID. The default uses packet.flow_id, giving
        per-flow DRR. Flows mapped to one class share a FIFO and deficit counter.
    mtu_bytes: int
        Configured packet-size scale in bytes. The smallest-weight class receives
        max(MIN_QUANTUM, mtu_bytes) bytes per visit; other quanta scale with weight.
        Quanta stay fixed. Larger packets accumulate credit across visits.
    zero_buffer: bool
        Does this server have a zero-length buffer? This is useful when multiple
        basic elements need to be put together to construct a more complex element
        with a unified buffer.
    zero_downstream_buffer: bool
        Does this server's downstream element have a zero-length buffer? If so, packets
        may queue up in this element's own buffer rather than be forwarded to the
        next-hop element.
    debug: bool
        If True, prints more verbose debug information.
    """

    MIN_QUANTUM = 1500

    def __init__(
        self,
        env: simpy.Environment,
        rate: float,
        weights: list | dict,
        flow_classes: Callable[[Packet], Hashable] = lambda p: p.flow_id,
        mtu_bytes: int = 1500,
        zero_buffer: bool = False,
        zero_downstream_buffer: bool = False,
        debug: bool = False,
    ) -> None:
        if not isfinite(rate) or rate <= 0:
            raise ValueError("rate must be finite and positive.")
        if not isfinite(mtu_bytes) or mtu_bytes <= 0:
            raise ValueError("mtu_bytes must be finite and positive.")
        self.env = env
        self.rate = rate
        self.weights = weights

        self.flow_classes = flow_classes

        self.weight_lookup = {}
        self.deficit = {}
        self.flow_queue_count = {}
        self.quantum = {}

        if isinstance(weights, list):
            iterable = enumerate(weights)
        elif isinstance(weights, dict):
            iterable = weights.items()
        else:
            raise ValueError("Weights must be either a list or a dictionary.")

        for queue_id, weight in iterable:
            if not isfinite(weight) or weight <= 0:
                raise ValueError("Every weight must be finite and positive.")
            self.weight_lookup[queue_id] = weight
            self.deficit[queue_id] = 0.0
            self.flow_queue_count[queue_id] = 0

        if not self.weight_lookup:
            raise ValueError("At least one weight is required.")
        self.min_weight = min(self.weight_lookup.values())
        self.base_quantum = max(self.MIN_QUANTUM, mtu_bytes)
        # A quantum is byte credit per class visit, not a packet-size estimate.
        # Observing a jumbo must not change the configured allocation to others.
        for queue_id, weight in self.weight_lookup.items():
            quantum = self.base_quantum * (weight / self.min_weight)
            if not isfinite(quantum):
                raise ValueError("weight ratios must produce finite quanta.")
            self.quantum[queue_id] = quantum

        # Hold an unaffordable head rather than putting it back behind its FIFO.
        self.head_of_line = {}
        self.active_set = set()
        self.active_queue = deque()
        # The class whose visit is in progress is separate from the waiting
        # active list. Arrivals must not insert a still-backlogged visit twice.
        # None is a valid dictionary class key, so idle needs a unique sentinel.
        self._no_current_queue = object()
        self.current_queue = self._no_current_queue

        # One FIFO queue for each flow_id or class_id
        self.stores = {}

        self.current_packet = None
        self.byte_sizes: dd[Hashable, float] = dd(lambda: 0)

        self.packets_available = simpy.Store(env)
        self.idle = True

        self.packets_received = 0
        self.out: Any = None

        self.upstream_updates = {}
        self.upstream_stores = {}

        self.zero_buffer = zero_buffer
        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_stores = {}

        self.debug = debug
        self.action = env.process(self.run())

    def _activate_flow(self, queue_id: Hashable) -> None:
        """Append a newly backlogged class after the waiting active classes."""
        if queue_id == self.current_queue or queue_id in self.active_set:
            return

        if self.flow_queue_count.get(queue_id, 0) == 0:
            return

        self.active_set.add(queue_id)
        self.active_queue.append(queue_id)

        if self.idle:
            self.idle = False
            self.packets_available.put(True)

    def update_stats(self, packet: Packet) -> None:
        """Charge selected bytes and remove them from waiting-queue accounting."""
        queue_id = self.flow_classes(packet)
        self.flow_queue_count[queue_id] -= 1
        self.byte_sizes[queue_id] -= packet.size
        self.deficit[queue_id] -= packet.size

        # DRR discards residual credit as soon as the waiting queue empties.
        # A packet arriving while this last packet serializes starts a new visit.
        if self.flow_queue_count[queue_id] == 0:
            self.deficit[queue_id] = 0.0
            self.current_queue = self._no_current_queue

        if self.debug:
            print(
                f"Selected packet {packet.packet_id} from flow {packet.flow_id} "
                f"belonging to class {queue_id}, deficit {self.deficit[queue_id]}"
            )

    def update(self, packet: Packet) -> None:
        """
        Propagate the downstream's shared-buffer release to the upstream.

        Directly injected packets may have no upstream hooks even in zero-buffer
        mode. A downstream calls this after removing our retained store reference.
        """
        if self.zero_buffer and packet in self.upstream_stores:
            # Clear hooks before callbacks, which may synchronously revisit us.
            store = self.upstream_stores.pop(packet)
            callback = self.upstream_updates.pop(packet)
            remove_packet(store, packet)
            callback(packet)

    def packet_in_service(self) -> Packet | None:
        """
        Returns the packet that is currently being sent to the downstream element.
        Used by a ServerMonitor.
        """
        return self.current_packet

    def byte_size(self, queue_id: Hashable) -> float:
        """
        Returns waiting bytes, excluding service and downstream-retained packets.
        Used by a ServerMonitor.
        """
        if queue_id in self.flow_queue_count:
            return self.byte_sizes[queue_id]

        return 0

    def size(self, queue_id: Hashable) -> int:
        """
        Returns waiting packets for a class, excluding the packet in service.
        Used by a ServerMonitor.
        """
        if queue_id in self.flow_queue_count:
            return self.flow_queue_count[queue_id]

        return 0

    def all_flows(self) -> list[Hashable]:
        """
        Returns the observed class IDs (flow IDs with the default classifier).
        """
        return list(self.byte_sizes)

    def total_packets(self) -> int:
        """
        Returns the total number of waiting packets across all classes.
        """
        return sum(self.flow_queue_count.values())

    def run(self) -> Generator[simpy.Event, Any, None]:
        """Wait for active classes, then serialize chosen packets without preemption.

        Logical deficit rounds take no simulation time. A zero-time visit wait
        lets already scheduled arrivals at this time join selection. Retrieval
        and each packet's byte-to-bit serialization delay also yield. This local
        wait does not impose global event phases on arbitrary user processes.
        """
        while True:
            if not self.active_queue:
                self.idle = True
                yield self.packets_available.get()
                self.idle = False
                continue

            # Let scheduled arrivals join before scanning another logical visit,
            # including when a jumbo needs several visits with no service yet.
            yield self.env.timeout(0)
            queue_id = self.active_queue.popleft()
            self.active_set.discard(queue_id)

            if self.flow_queue_count.get(queue_id, 0) == 0:
                self.head_of_line.pop(queue_id, None)
                self.deficit[queue_id] = 0.0
                continue

            self.current_queue = queue_id
            self.deficit[queue_id] += self.quantum[queue_id]
            if self.debug:
                print(
                    f"Flow queue length: {self.flow_queue_count}, ",
                    f"deficit counters: {self.deficit}",
                )

            while self.deficit[queue_id] > 0 and self.flow_queue_count[queue_id] > 0:
                if queue_id in self.head_of_line:
                    packet = self.head_of_line[queue_id]
                    del self.head_of_line[queue_id]
                else:
                    if self.zero_downstream_buffer:
                        ds_store = self.downstream_stores[queue_id]
                        packet = yield ds_store.get()
                    else:
                        store = self.stores[queue_id]
                        packet = yield store.get()

                assert queue_id == self.flow_classes(packet)

                if packet.size <= self.deficit[queue_id]:
                    # Selection spends byte credit now. Transmission itself is
                    # non-preemptive even if another class becomes eligible.
                    self.update_stats(packet)
                    self.current_packet = packet
                    # Sizes are bytes; 8 * bytes / bits-per-second is seconds.
                    yield self.env.timeout(packet.size * 8.0 / self.rate)
                    self.current_packet = None

                    if self.zero_downstream_buffer:
                        self.out.put(
                            packet,
                            upstream_update=self.update,
                            upstream_store=self.stores[queue_id],
                        )
                    else:
                        self.update(packet)
                        self.out.put(packet)

                    if self.current_queue is self._no_current_queue:
                        # That selection emptied the queue. Arrivals during its
                        # service have already reactivated it at the list tail.
                        break
                else:
                    assert queue_id not in self.head_of_line
                    self.head_of_line[queue_id] = packet
                    break

            self.current_queue = self._no_current_queue
            if self.flow_queue_count.get(queue_id, 0) > 0:
                self._activate_flow(queue_id)
            else:
                self.deficit[queue_id] = 0.0

    def put(
        self, packet: Packet,
        upstream_update: Callable[[Packet], None] | None = None,
        upstream_store: Any = None,
    ) -> simpy.Event:
        """Sends a packet to this element."""
        flow_class = self.flow_classes(packet)
        if flow_class not in self.weight_lookup:
            raise ValueError(f"No weight configured for class {flow_class!r}.")
        self.packets_received += 1
        self.byte_sizes[flow_class] += packet.size

        if self.debug:
            print(
                f"Packet arrived at {self.env.now}, flow_id {packet.flow_id}, "
                f"belonging to class {flow_class} "
                f"packet_id {packet.packet_id}, "
                f"deficit {self.deficit[flow_class]}, "
                f"deficit counters: {self.deficit}"
            )

        if flow_class not in self.stores:
            self.stores[flow_class] = simpy.Store(self.env)

            if self.zero_downstream_buffer:
                self.downstream_stores[flow_class] = simpy.Store(self.env)

        self.flow_queue_count[flow_class] += 1
        self._activate_flow(flow_class)

        if (
            self.zero_buffer
            and upstream_update is not None
            and upstream_store is not None
        ):
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update

        if self.zero_downstream_buffer:
            self.downstream_stores[flow_class].put(packet)

        return self.stores[flow_class].put(packet)
