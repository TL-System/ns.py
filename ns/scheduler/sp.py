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
        The bit rate of the port.
    priorities: list or dict
        This can be either a list or a dictionary. If it is a list, it uses the flow_id ---
        or class_id, if class-based static priority scheduling is activated using the
        `flow_classes' parameter below --- as its index to look for the flow (or class)'s
        corresponding priority. If it is a dictionary, it contains (flow_id or class_id
        -> priority) pairs for each possible flow_id or class_id.
    flow_classes: function
        This is a function that matches a packet's flow_ids to class_ids, used to implement
        class-based Deficit Round Robin. The default is a lambda function that uses a packet's
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

    def __init__(self,
                 env,
                 rate,
                 priorities,
                 flow_classes: Callable = lambda p: p.flow_id,
                 zero_buffer=False,
                 zero_downstream_buffer=False,
                 debug=False) -> None:
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
            raise ValueError(
                'Priorities must be either a list or a dictionary.')

        for prio in priorities_list:
            if prio not in self.prio_queue_count:
                self.prio_queue_count[prio] = 0

        self.priorities_list = sorted(self.prio_queue_count, reverse=True)

        self.packets_available = simpy.Store(self.env)

        self.current_packet = None

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
        """
        The packet has been sent (or authorized to be sent if this scheduler has a zero-buffer
        configuration), we need to update the internal statistics related to this event.
        """
        self.prio_queue_count[packet.prio[self.element_id]] -= 1

        if self.flow_classes(packet) in self.byte_sizes:
            self.byte_sizes[self.flow_classes(packet)] -= packet.size
        else:
            raise ValueError("Error: the packet is from an unrecorded flow.")

        if self.debug:
            print(
                f"Sent out packet {packet.packet_id} from flow {packet.flow_id} "
                f"belonging to class {self.flow_classes(packet)} "
                f"of priority {packet.prio[self.element_id]}")

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
            return self.byte_sizes[queue_id]

        return 0

    def size(self, queue_id) -> int:
        """
        Returns the size of the queue for a particular queue_id, in the
        number of packets. Used by a ServerMonitor.
        """
        if queue_id in self.stores:
            return len(self.stores[queue_id].items)

        return 0

    def all_flows(self) -> list:
        """
        Returns a list containing all the flow IDs.
        """
        return self.byte_sizes.keys()

    def total_packets(self) -> int:
        """
        Returns the total number of packets currently in the queues.
        """
        return sum(self.prio_queue_count.values())

    def run(self):
        """The generator function used in simulations."""
        while True:
            for prio in self.priorities_list:
                if self.prio_queue_count[prio] > 0:
                    if self.zero_downstream_buffer:
                        ds_store = self.downstream_stores[prio]
                        packet = yield ds_store.get()
                        packet.prio[self.element_id] = prio

                        self.current_packet = packet
                        yield self.env.timeout(packet.size * 8.0 / self.rate)

                        self.update_stats(packet)
                        self.out.put(packet,
                                     upstream_update=self.update,
                                     upstream_store=self.stores[prio])
                        self.current_packet = None
                    else:
                        store = self.stores[prio]
                        packet = yield store.get()
                        packet.prio[self.element_id] = prio

                        self.current_packet = packet
                        yield self.env.timeout(packet.size * 8.0 / self.rate)

                        self.update_stats(packet)
                        self.update(packet)
                        self.out.put(packet)
                        self.current_packet = None

                    break

            if self.total_packets() == 0:
                yield self.packets_available.get()

    def put(self, packet, upstream_update=None, upstream_store=None):
        """ Sends a packet to this element. """
        self.packets_received += 1
        self.byte_sizes[self.flow_classes(packet)] += packet.size

        if self.total_packets() == 0:
            self.packets_available.put(True)

        prio = self.prio[self.flow_classes(packet)]
        self.prio_queue_count[prio] += 1

        if self.debug:
            print(
                "At time {:.2f}: received packet {:d} from flow {} belonging to class {}"
                .format(self.env.now, packet.packet_id, packet.flow_id,
                        self.flow_classes(packet)))

        if not prio in self.stores:
            self.stores[prio] = simpy.Store(self.env)

            if self.zero_downstream_buffer:
                self.downstream_stores[prio] = simpy.Store(self.env)

        if self.zero_buffer and upstream_update is not None and upstream_store is not None:
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update

        if self.zero_downstream_buffer:
            self.downstream_stores[prio].put(packet)

        return self.stores[prio].put(packet)
