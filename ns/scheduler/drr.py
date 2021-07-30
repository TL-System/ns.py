"""
Implements a Deficit Round Robin (DRR) server.

Reference:

M. Shreedhar and G. Varghese, "Efficient Fair Queuing Using Deficit Round-Robin," IEEE/ACM
Tran. Networking, vol. 4, no. 3, June 1996.
"""

from collections import defaultdict as dd
from collections.abc import Callable

import simpy
from ns.packet.packet import Packet


class DRRServer:
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
        below --- as its index to look for the flow's corresponding weight. If it is a dictionary,
        it contains (flow_id or class_id -> weight) pairs for each possible flow_id or class_id.
    flow_classes: function
        This is a function that matches flow_id's to class_ids, used to implement class-based
        Deficit Round Robin. The default is an identity lambda function, which is equivalent to
        flow-based DRR.
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

    def __init__(self,
                 env,
                 rate,
                 weights: list,
                 flow_classes: Callable = lambda x: x,
                 zero_buffer=False,
                 zero_downstream_buffer=False,
                 debug: bool = False) -> None:
        self.env = env
        self.rate = rate
        self.weights = weights

        self.flow_classes = flow_classes

        self.deficit = {}
        self.flow_queue_count = {}
        self.quantum = {}

        if isinstance(weights, list):
            for queue_id, weight in enumerate(weights):
                self.deficit[queue_id] = 0.0
                self.flow_queue_count[queue_id] = 0
                self.quantum[queue_id] = self.MIN_QUANTUM * weight / min(
                    weights)

        elif isinstance(weights, dict):
            for (queue_id, value) in weights.items():
                self.deficit[queue_id] = 0.0
                self.flow_queue_count[queue_id] = 0
                self.quantum[queue_id] = self.MIN_QUANTUM * value / min(
                    weights.values())
        else:
            raise ValueError('Weights must be either a list or a dictionary.')

        self.head_of_line = {}
        self.active_set = set()

        # One FIFO queue for each flow_id or class_id
        self.stores = {}

        self.current_packet = None
        self.byte_sizes = dd(lambda: 0)

        self.packets_available = simpy.Store(env)

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

    def update(self, packet):
        """The packet has just been retrieved from this element's own buffer, so
        update internal housekeeping states accordingly."""
        if self.zero_buffer:
            self.upstream_stores[packet].get()
            del self.upstream_stores[packet]
            self.upstream_updates[packet](packet)
            del self.upstream_updates[packet]

        if self.debug:
            print(
                f"Sent out packet {packet.packet_id} from flow {packet.flow_id} "
                f"belonging to class {self.flow_classes(packet.flow_id)}")

        if self.debug:
            print(
                f"Deficit reduced to {self.deficit[packet.flow_id]} for flow {packet.flow_id}"
            )

        self.flow_queue_count[self.flow_classes(packet.flow_id)] -= 1

        if self.flow_queue_count[self.flow_classes(packet.flow_id)] == 0:
            self.deficit[self.flow_classes(packet.flow_id)] = 0.0

        if self.flow_classes(packet.flow_id) in self.byte_sizes:
            self.byte_sizes[self.flow_classes(packet.flow_id)] -= packet.size
        else:
            raise ValueError(
                "Error: the packet to be sent has never been received.")

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
        if queue_id in self.flow_queue_count:
            return self.byte_sizes[queue_id]

        return 0

    def size(self, queue_id) -> int:
        """
        Returns the size of the queue for a particular queue_id, in the
        number of packets. Used by a ServerMonitor.
        """
        if queue_id in self.flow_queue_count:
            return self.flow_queue_count[queue_id]

        return 0

    def all_flows(self) -> list:
        """
        Returns a list containing all the flow IDs.
        """
        return self.byte_sizes.keys()

    def total_packets(self) -> int:
        return sum(self.flow_queue_count.values())

    def run(self):
        """The generator function used in simulations."""
        while True:
            while self.total_packets() > 0:
                flow_queue_counts = self.flow_queue_count.items()

                for queue_id, count in flow_queue_counts:
                    if count > 0:
                        self.deficit[queue_id] += self.quantum[queue_id]
                        if self.debug:
                            print(
                                f"Flow queue length: {self.flow_queue_count}, ",
                                f"deficit counters: {self.deficit}")

                    while self.deficit[queue_id] > 0 and self.flow_queue_count[
                            queue_id] > 0:
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

                        assert queue_id == self.flow_classes(packet.flow_id)

                        if packet.size <= self.deficit[queue_id]:
                            self.current_packet = packet
                            yield self.env.timeout(packet.size * 8.0 /
                                                   self.rate)

                            if self.zero_downstream_buffer:
                                self.out.put(
                                    packet,
                                    upstream_update=self.update,
                                    upstream_store=self.stores[queue_id])
                            else:
                                self.update(packet)
                                self.out.put(packet)

                            self.deficit[self.flow_classes(
                                packet.flow_id)] -= packet.size
                            self.current_packet = None
                        else:
                            assert not queue_id in self.head_of_line
                            self.head_of_line[queue_id] = packet
                            break

            # No more packets in the scheduler to process at this time
            yield self.packets_available.get()

    def put(self, packet, upstream_update=None, upstream_store=None):
        """ Sends a packet to this element. """
        self.packets_received += 1
        flow_id = packet.flow_id

        self.byte_sizes[self.flow_classes(flow_id)] += packet.size

        if self.debug:
            print(
                f"Packet arrived at {self.env.now}, flow_id {flow_id}, "
                f"belonging to class {self.flow_classes(flow_id)} "
                f"packet_id {packet.packet_id}, deficit {self.deficit[self.flow_classes(flow_id)]}, "
                f"deficit counters: {self.deficit}")

        if not self.flow_classes(flow_id) in self.stores:
            self.stores[self.flow_classes(flow_id)] = simpy.Store(self.env)

            if self.zero_downstream_buffer:
                self.downstream_stores[self.flow_classes(
                    flow_id)] = simpy.Store(self.env)

        if self.total_packets() == 0:
            self.packets_available.put(True)

        self.flow_queue_count[self.flow_classes(flow_id)] += 1

        if self.zero_buffer and upstream_update is not None and upstream_store is not None:
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update

        if self.zero_downstream_buffer:
            self.downstream_stores[self.flow_classes(flow_id)].put(packet)

        return self.stores[self.flow_classes(flow_id)].put(packet)
