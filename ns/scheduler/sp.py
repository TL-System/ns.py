"""
Implements a Static Priority (SP) server.
"""

import uuid
from collections import defaultdict as dd
from collections.abc import Callable

import simpy
from ns.packet.packet import Packet


class SPServer:
    """
    Parameters
    ----------
    env: simpy.Environment
        The simulation environment.
    rate: float
        The positive bit rate of the port.
    priorities: list or dict
        This can be either a list or a dictionary. If it is a list, it uses the flow_id ---
        or class_id, if class-based static priority scheduling is activated using the
        `flow_classes' parameter below --- as its index to look for the flow (or class)'s
        corresponding priority. If it is a dictionary, it contains (flow_id or class_id
        -> priority) pairs for each possible flow_id or class_id. Larger numbers
        have higher priority; classes with equal priority share one FIFO.
    flow_classes: function
        This is a function that matches a packet's flow_ids to class_ids, used to implement
        class-based Static Priority. The default is a lambda function that uses a packet's
        flow_id as its class_id, which is equivalent to flow-based Static Priority.
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
        env,
        rate,
        priorities,
        flow_classes: Callable = lambda p: p.flow_id,
        zero_buffer=False,
        zero_downstream_buffer=False,
        debug=False,
    ) -> None:
        self.env = env
        self.rate = rate
        self.prio = priorities
        self.flow_classes = flow_classes

        self.element_id = uuid.uuid1()
        self.stores = {}
        self.prio_queue_count = {}

        if isinstance(priorities, list):
            priorities_list = priorities
        elif isinstance(priorities, dict):
            priorities_list = priorities.values()
        else:
            raise ValueError("Priorities must be either a list or a dictionary.")

        for prio in priorities_list:
            if prio not in self.prio_queue_count:
                self.prio_queue_count[prio] = 0

        self.priorities_list = sorted(self.prio_queue_count, reverse=True)

        self.packets_available = simpy.Store(self.env)

        self.current_packet = None

        # Counters describe packets waiting for local service, keyed by class.
        # A priority bucket may contain several distinct classes and flow IDs.
        self.flow_queue_count = dd(lambda: 0)
        self.byte_sizes = dd(lambda: 0)

        self.packets_received = 0
        self.out = None
        self.upstream_updates = {}
        self.upstream_stores = {}
        self.zero_buffer = zero_buffer
        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_stores = {}

        self.debug = debug
        self.action = env.process(self.run())

    def update_stats(self, packet):
        """Remove a selected packet from the waiting counters at service start."""
        self.prio_queue_count[packet.prio[self.element_id]] -= 1
        class_id = self.flow_classes(packet)
        self.flow_queue_count[class_id] -= 1
        self.byte_sizes[class_id] -= packet.size

        if self.debug:
            print(
                f"Started packet {packet.packet_id} from flow {packet.flow_id} "
                f"belonging to class {class_id} "
                f"of priority {packet.prio[self.element_id]}"
            )

    def update(self, packet):
        """
        The packet has just been retrieved from this element's own buffer by a downstream
        node that has no buffers. Propagate to the upstream if this node also has a zero-buffer
        configuration.
        """
        if self.zero_buffer and packet in self.upstream_stores:
            store = self.upstream_stores.pop(packet)
            callback = self.upstream_updates.pop(packet)
            # SP can select a packet behind another priority in a shared FIFO.
            # Move only that packet to the head before using Store.get(), which
            # preserves the remaining FIFO order and wakes pending puts normally.
            # Minimal upstream adapters without .items retain the legacy get API.
            if hasattr(store, "items"):
                index = next(i for i, item in enumerate(store.items) if item is packet)
                store.items.insert(0, store.items.pop(index))
            store.get()
            callback(packet)

    def packet_in_service(self) -> Packet:
        """
        Returns the packet that is currently being sent to the downstream element.
        Used by a ServerMonitor.
        """
        return self.current_packet

    def byte_size(self, queue_id) -> int:
        """
        Returns waiting bytes for a flow class, excluding the packet in service
        and packets retained only for downstream ownership.
        Used by a ServerMonitor.
        """
        if queue_id in self.byte_sizes:
            return self.byte_sizes[queue_id]

        return 0

    def size(self, queue_id) -> int:
        """
        Returns the number of packets waiting for a flow class's local service.
        This uses the same class IDs as byte_size(), not priority bucket IDs.
        """
        return self.flow_queue_count.get(queue_id, 0)

    def all_flows(self) -> list:
        """
        Returns the observed class IDs (flow IDs with the default mapping).
        """
        return list(self.byte_sizes)

    def total_packets(self) -> int:
        """
        Returns the total number of packets waiting for local service.
        """
        return sum(self.prio_queue_count.values())

    def run(self):
        """Wait for work, choose the highest priority, and serialize one packet.

        Service is nonpreemptive. A zero-time selection wait lets already
        scheduled arrivals at a completion time join the next decision; it does
        not impose global event phases on arbitrary chains of user processes.
        """
        while True:
            while self.total_packets() == 0:
                yield self.packets_available.get()

            # Reconsider priority at every service start, after same-time arrivals.
            yield self.env.timeout(0)
            for prio in self.priorities_list:
                if self.prio_queue_count[prio] > 0:
                    if self.zero_downstream_buffer:
                        store = self.downstream_stores[prio]
                    else:
                        store = self.stores[prio]
                    packet = yield store.get()
                    packet.prio[self.element_id] = prio

                    self.current_packet = packet
                    self.update_stats(packet)
                    # Packet sizes are bytes; multiplying by 8 converts to bits.
                    yield self.env.timeout(packet.size * 8.0 / self.rate)

                    # A synchronous out.put() should observe completed service.
                    self.current_packet = None
                    if self.zero_downstream_buffer:
                        self.out.put(
                            packet,
                            upstream_update=self.update,
                            upstream_store=self.stores[prio],
                        )
                    else:
                        self.update(packet)
                        self.out.put(packet)
                    break

    def put(self, packet, upstream_update=None, upstream_store=None):
        """Sends a packet to this element."""
        class_id = self.flow_classes(packet)
        prio = self.prio[class_id]
        self.packets_received += 1
        self.flow_queue_count[class_id] += 1
        self.byte_sizes[class_id] += packet.size

        # A single wakeup is enough even if the sole waiting packet repeatedly
        # enters service before another arrives. Do not accumulate idle tokens.
        if self.total_packets() == 0 and not self.packets_available.items:
            self.packets_available.put(True)

        self.prio_queue_count[prio] += 1

        if self.debug:
            print(
                "At time {:.2f}: received packet {:d} from flow {} belonging to class {}".format(
                    self.env.now,
                    packet.packet_id,
                    packet.flow_id,
                    class_id,
                )
            )

        if prio not in self.stores:
            self.stores[prio] = simpy.Store(self.env)

            if self.zero_downstream_buffer:
                self.downstream_stores[prio] = simpy.Store(self.env)

        if (
            self.zero_buffer
            and upstream_update is not None
            and upstream_store is not None
        ):
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update

        if self.zero_downstream_buffer:
            self.downstream_stores[prio].put(packet)

        return self.stores[prio].put(packet)
