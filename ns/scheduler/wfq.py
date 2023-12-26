"""
Implements a Weighted Fair Queueing (WFQ) server.

Reference:

A. K. Parekh, R. G. Gallager, "A Generalized Processor Sharing Approach to Flow Control
in Integrated Services Networks: The Single-Node Case," IEEE/ACM Trans. Networking,
vol. 1, no. 3, pp. 344-357, June 1993.

https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=234856
"""
from collections import defaultdict as dd
from collections.abc import Callable

from ns.packet.packet import Packet
from ns.utils import taggedstore


class WFQServer:
    """
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
        or class_id.
    flow_classes: function
        This is a function that matches a packet's flow_ids to class_ids, used to implement
        class-based Deficit Round Robin. The default is a lambda function that uses a packet's
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
        env,
        rate: float,
        weights,
        flow_classes: Callable = lambda p: p.flow_id,
        zero_buffer=False,
        zero_downstream_buffer=False,
        debug: bool = False,
    ) -> None:
        self.env = env
        self.rate = rate
        self.weights = weights

        self.flow_classes = flow_classes
        self.finish_times = {}
        self.flow_queue_count = {}

        if isinstance(weights, list):
            for queue_id in range(len(weights)):
                self.finish_times[queue_id] = 0.0
                self.flow_queue_count[queue_id] = 0

        elif isinstance(weights, dict):
            for queue_id, __ in weights.items():
                self.finish_times[queue_id] = 0.0
                self.flow_queue_count[queue_id] = 0
        else:
            raise ValueError("Weights must be either a list or a dictionary.")

        self.active_set = set()
        self.vtime = 0.0
        self.out = None
        self.packets_received = 0
        self.packets_dropped = 0
        self.debug = debug

        self.current_packet = None
        self.byte_sizes = dd(lambda: 0)

        self.upstream_updates = {}
        self.upstream_stores = {}
        self.zero_buffer = zero_buffer
        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_store = taggedstore.TaggedStore(env)

        self.store = taggedstore.TaggedStore(env)
        self.action = env.process(self.run())
        self.last_update = 0.0

    def update_stats(self, packet):
        """
        The packet has been sent (or authorized to be sent if the downstream node has a zero-buffer
        configuration), we need to update the internal statistics related to this event.
        """

        weight_sum = 0.0
        now = self.env.now

        # Updating the virtual time based on the current set of active flow classes
        for i in self.active_set:
            weight_sum += self.weights[i]

        self.vtime += (now - self.last_update) / weight_sum

        # Computing the new set of active flow classes
        self.flow_queue_count[self.flow_classes(packet)] -= 1

        if self.flow_queue_count[self.flow_classes(packet)] == 0:
            self.active_set.remove(self.flow_classes(packet))

        if len(self.active_set) == 0:
            self.vtime = 0.0
            for queue_id, __ in self.finish_times.items():
                self.finish_times[queue_id] = 0.0

        self.last_update = now

        if self.flow_classes(packet) in self.byte_sizes:
            self.byte_sizes[self.flow_classes(packet)] -= packet.size
        else:
            raise ValueError("Error: the packet is from an unrecorded flow.")

        if self.debug:
            print(
                f"Sent Packet {packet.packet_id} from flow {packet.flow_id} "
                f"belonging to class {self.flow_classes(packet)} at time {now}."
            )

    def update(self, packet):
        """
        The packet has just been retrieved from this element's own buffer by a downstream
        node that has no buffers. Propagate to the upstream if this node also has a zero-buffer
        configuration.
        """
        # With no local buffers, this element needs to pull the packet from upstream
        if self.zero_buffer:
            # For each packet, remove it from its own upstream's store
            self.upstream_stores[packet].get()
            del self.upstream_stores[packet]
            self.upstream_updates[packet](packet)
            del self.upstream_updates[packet]

    def packet_in_service(self) -> Packet:
        """
        Returns the packet that is currently being sent to the downstream element.
        Used by a ServerMonitor.
        """
        return self.current_packet

    def byte_size(self, queue_id) -> int:
        """
        Returns the size of the queue for a particular queue_id, in bytes.
        Used by a ServerMonitor.
        """
        if queue_id in self.byte_sizes:
            return int(self.byte_sizes[queue_id])

        return 0

    def size(self, queue_id) -> int:
        """
        Returns the size of the queue for a particular queue_id, in the
        number of packets. Used by a ServerMonitor.
        """
        return self.flow_queue_count[queue_id]

    def all_flows(self) -> list:
        """
        Returns a list containing all the queue IDs, which may be flow IDs or class IDs
        (in the case of class-based WFQ).
        """
        return list(self.byte_sizes.keys())

    def run(self):
        """The generator function used in simulations."""
        while True:
            if self.zero_downstream_buffer:
                packet = yield self.downstream_store.get()
                self.current_packet = packet
                yield self.env.timeout(packet.size * 8.0 / self.rate)

                self.update_stats(packet)
                self.out.put(
                    packet, upstream_update=self.update, upstream_store=self.store
                )
                self.current_packet = None
            else:
                packet = yield self.store.get()

                self.current_packet = packet
                yield self.env.timeout(packet.size * 8.0 / self.rate)

                self.update_stats(packet)
                self.update(packet)
                self.out.put(packet)
                self.current_packet = None

    def put(self, packet, upstream_update=None, upstream_store=None):
        """Sends a packet to this element."""
        self.packets_received += 1
        flow_id = packet.flow_id

        # Updating the virtual time and the finish time for each flow class
        now = self.env.now

        if len(self.active_set) == 0:
            self.vtime = 0.0
            for queue_id, __ in self.finish_times.items():
                self.finish_times[queue_id] = 0.0
        else:
            weight_sum = 0.0

            for i in self.active_set:
                weight_sum += self.weights[i]

            self.vtime += (now - self.last_update) / weight_sum
            self.finish_times[self.flow_classes(packet)] = max(
                self.finish_times[self.flow_classes(packet)], self.vtime
            ) + packet.size * 8.0 / (
                self.rate * self.weights[self.flow_classes(packet)]
            )

        # Updating the byte sizes, the flow queue count, and the set of active flows
        self.byte_sizes[self.flow_classes(packet)] += packet.size
        self.flow_queue_count[self.flow_classes(packet)] += 1
        self.active_set.add(self.flow_classes(packet))

        if self.debug:
            print(
                f"Packet arrived at {now}, with flow_id {flow_id}, "
                f"belonging to class {self.flow_classes(packet)}, "
                f"packet_id {packet.packet_id}, "
                f"finish_time {self.finish_times[self.flow_classes(packet)]}"
            )

        self.last_update = now

        if (
            self.zero_buffer
            and upstream_update is not None
            and upstream_store is not None
        ):
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update

        if self.zero_downstream_buffer:
            self.downstream_store.put(
                (self.finish_times[self.flow_classes(packet)], packet)
            )

        return self.store.put((self.finish_times[self.flow_classes(packet)], packet))
