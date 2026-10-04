"""
Implements packet-active Weighted Fair Queueing (WFQ), matching Days.

This is the Days queued-plus-in-service recurrence, an approximation to the
fluid GPS reference in the paper below. A class contributes its weight until
its last physical packet completes; fluid backlog may drain at a different time.

Reference:

A. K. Parekh, R. G. Gallager, "A Generalized Processor Sharing Approach to Flow Control
in Integrated Services Networks: The Single-Node Case," IEEE/ACM Trans. Networking,
vol. 1, no. 3, pp. 344-357, June 1993.

https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=234856
"""

from collections import defaultdict as dd
from collections.abc import Callable, Generator, Hashable
from math import isfinite
from typing import Any

import simpy

from ns.packet.packet import Packet
from ns.utils import taggedstore
from ns.utils.retained_store import remove_packet


class WFQServer:
    """Select the smallest weighted finish tag for nonpreemptive service.

    Virtual time and finish tags use seconds of normalized link service. While
    work is active, V advances by elapsed real time / sum of active weights.
    An arrival receives max(V, its class's previous finish) + serialization
    time / weight. All flows in a class share that finish history. When no packet
    is waiting or in service, V and every class history reset for the next busy
    period. Packets retained only for downstream ownership are not active.
    Days scales these tags by the common link rate and uses exact rationals;
    this simulator retains floating-point seconds and SimPy's local event order.

    Parameters
    ----------
    env: simpy.Environment
        The simulation environment.
    rate: float
        The bit rate of the port.
    weights: list or dict
        This can be either a list or a dictionary. If it is a list, it uses the flow_id ---
        or class_id, if class-based fair queueing is activated using the `flow_classes' parameter
        below --- as its index to look for the flow (or class)'s corresponding weight. If it is a
        dictionary, it contains (flow_id or class_id -> weight) pairs for each possible flow_id
        or class_id. Every weight must be positive and finite.
    flow_classes: function
        This is a function that matches a packet's flow_ids to class_ids, used to implement
        class-based WFQ. The default is a lambda function that uses a packet's
        flow_id as its class_id, which is equivalent to flow-based WFQ.
    zero_buffer: bool
        Does this server have a zero-length buffer? This is useful when multiple
        basic elements need to be put together to construct a more complex element
        with a unified buffer.
    zero_downstream_buffer: bool
        Does this server's downstream element has a zero-length buffer? If so, packets
        may queue up in this element's own buffer rather than be forwarded to the
        next-hop element.
    debug: bool
        If True, prints more verbose debug information.
    """

    def __init__(
        self,
        env: simpy.Environment,
        rate: float,
        weights: Any,
        flow_classes: Callable[[Packet], Hashable] = lambda p: p.flow_id,
        zero_buffer: bool = False,
        zero_downstream_buffer: bool = False,
        debug: bool = False,
    ) -> None:
        if not isfinite(rate) or rate <= 0:
            raise ValueError("The link rate must be positive and finite.")
        if not isinstance(weights, (list, dict)) or not weights:
            raise ValueError("Weights must be a nonempty list or dictionary.")

        self.env = env
        self.rate = rate
        self.weights = weights

        self.flow_classes = flow_classes
        self.finish_times = {}
        # Waiting telemetry is separate from queued-plus-in-service activity.
        self.flow_queue_count = {}
        self.active_packets = {}

        if isinstance(weights, list):
            queue_ids = range(len(weights))
        else:
            queue_ids = weights
        for queue_id in queue_ids:
            if not isfinite(weights[queue_id]) or weights[queue_id] <= 0:
                raise ValueError("Each weight must be positive and finite.")
            self.finish_times[queue_id] = 0.0
            self.flow_queue_count[queue_id] = 0
            self.active_packets[queue_id] = 0

        self.active_set = set()
        self.vtime = 0.0
        self.out: Any = None
        self.packets_received = 0
        self.packets_dropped = 0
        self.debug = debug

        self.current_packet = None
        self.byte_sizes: dd[Hashable, float] = dd(lambda: 0)

        self.upstream_updates = {}
        self.upstream_stores = {}
        self.zero_buffer = zero_buffer
        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_store = taggedstore.TaggedStore(env)

        self.store = taggedstore.TaggedStore(env)
        self.last_update = 0.0
        # Wake service without a pending heap get reserving the first arrival.
        self._wakeup = env.event()
        self.action = env.process(self.run())

    def _advance_virtual_time(self) -> None:
        """Advance using classes active during the elapsed physical interval."""
        weight_sum = sum(self.weights[class_id] for class_id in self.active_set)
        self.vtime += (self.env.now - self.last_update) / weight_sum
        self.last_update = self.env.now

    def update_stats(self, packet: Packet) -> None:
        """Finish local service, then retire the class if no active packets remain.

        Advance V before removing the in-service packet's weight. A packet held
        only for downstream ownership is no longer active in this recurrence.
        """
        now = self.env.now
        class_id = self.flow_classes(packet)
        self._advance_virtual_time()
        self.active_packets[class_id] -= 1
        if self.active_packets[class_id] == 0:
            self.active_set.remove(class_id)
        if not self.active_set:
            self.vtime = 0.0
            for queue_id in self.finish_times:
                self.finish_times[queue_id] = 0.0

        if self.debug:
            print(
                f"Sent Packet {packet.packet_id} from flow {packet.flow_id} "
                f"belonging to class {class_id} at time {now}."
            )

    def update(self, packet: Packet) -> None:
        """
        The packet has just been retrieved from this element's own buffer by a downstream
        node that has no buffers. Propagate to the upstream if this node also has a zero-buffer
        configuration.
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
        Returns bytes waiting for local service in a flow class.
        Service and downstream-retained ownership are excluded.
        Used by a ServerMonitor.
        """
        return self.byte_sizes.get(queue_id, 0)

    def size(self, queue_id: Hashable) -> int:
        """
        Returns packets waiting for local service in a flow class.
        Used by a ServerMonitor; service is reported separately.
        """
        return self.flow_queue_count.get(queue_id, 0)

    def total_packets(self) -> int:
        """Return the total number of packets waiting for local service."""
        return sum(self.flow_queue_count.values())

    def all_flows(self) -> list[Hashable]:
        """
        Returns observed class IDs (flow IDs with the default mapping).
        """
        return list(self.byte_sizes.keys())

    def run(self) -> Generator[simpy.Event, Any, None]:
        """Wait for work, choose the smallest tag, and serialize one packet.

        Service is nonpreemptive. A zero-time selection wait includes arrivals
        already scheduled at a completion time, without imposing global event
        phases on arbitrary chains of user processes. Equal tags retain the
        TaggedStore's admission order, including ties across distinct classes.
        """
        queue = self.downstream_store if self.zero_downstream_buffer else self.store
        while True:
            if not queue.items:
                self._wakeup = self.env.event()
                yield self._wakeup

            yield self.env.timeout(0)
            packet = yield queue.get()
            self.current_packet = packet
            class_id = self.flow_classes(packet)
            self.flow_queue_count[class_id] -= 1
            self.byte_sizes[class_id] -= packet.size
            # Packet sizes are bytes; multiplying by 8 converts to link bits.
            yield self.env.timeout(packet.size * 8.0 / self.rate)

            self.update_stats(packet)
            # Clear service before synchronous upstream or downstream callbacks.
            self.current_packet = None
            if self.zero_downstream_buffer:
                # Ownership stays in store until a downstream exact-object pull.
                self.out.put(
                    packet, upstream_update=self.update, upstream_store=self.store
                )
            else:
                self.update(packet)
                self.out.put(packet)

    def put(
        self, packet: Packet,
        upstream_update: Callable[[Packet], None] | None = None,
        upstream_store: Any = None,
    ) -> simpy.Event:
        """Assign a weighted finish tag and admit a packet to its flow class."""
        class_id = self.flow_classes(packet)
        # A missing class must fail before changing counters or virtual history.
        previous_finish = self.finish_times[class_id]
        weight = self.weights[class_id]
        now = self.env.now

        if not self.active_set:
            self.vtime = 0.0
            for queue_id in self.finish_times:
                self.finish_times[queue_id] = 0.0
            previous_finish = 0.0
        else:
            self._advance_virtual_time()

        # Bytes * 8 / bits-per-second gives seconds; divide by class weight.
        # The first packet in an idle system receives this increment too.
        tag = max(previous_finish, self.vtime) + packet.size * 8.0 / self.rate / weight
        self.finish_times[class_id] = tag
        self.last_update = now
        self.packets_received += 1
        self.byte_sizes[class_id] += packet.size
        self.flow_queue_count[class_id] += 1
        self.active_packets[class_id] += 1
        self.active_set.add(class_id)

        if self.debug:
            print(
                f"Packet arrived at {now}, with flow_id {packet.flow_id}, "
                f"belonging to class {class_id}, "
                f"packet_id {packet.packet_id}, "
                f"finish_time {tag}"
            )

        if (
            self.zero_buffer
            and upstream_update is not None
            and upstream_store is not None
        ):
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update

        if self.zero_downstream_buffer:
            self.downstream_store.put((tag, packet))

        admitted = self.store.put((tag, packet))
        if not self._wakeup.triggered:
            self._wakeup.succeed()
        return admitted
