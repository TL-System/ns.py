"""
Implements a Deficit Round Robin (DRR) server.

Reference:

M. Shreedhar and G. Varghese, "Efficient Fair Queuing Using Deficit Round-Robin," IEEE/ACM
Tran. Networking, vol. 4, no. 3, June 1996.
"""

from collections import defaultdict as dd

import simpy
from ns.packet.packet import Packet


class DRRServer:
    """
    Parameters
    ----------
    env: simpy.Environment
        the simulation environment
    rate: float
        the bit rate of the port
    weights: A list of weights for each possible packet flow_id. We assume a simple assignment
        of flow ids to weights, i.e., flow_id = 0 corresponds to weights[0], etc.
    zero_buffer: bool
        Does this server have a zero-length buffer? This is useful when multiple
        basic elements need to be put together to construct a more complex element
        with a unified buffer.
    zero_downstream_buffer: bool
        Does this server's downstream element has a zero-length buffer? If so, packets
        may queue up in this element's own buffer rather than be forwarded to the
        next-hop element.
    debug: bool
        Print more verbose debug information.
    """
    MIN_QUANTUM = 1500

    def __init__(self,
                 env,
                 rate,
                 weights,
                 zero_buffer=False,
                 zero_downstream_buffer=False,
                 debug=False,
                 out_queue_id=None) -> None:
        self.env = env
        self.rate = rate
        self.weights = weights
        self.out_queue_id = out_queue_id
        self.deficit = [0.0 for __ in range(len(weights))]
        self.head_of_line = {}
        self.flow_queue_count = [0 for __ in range(len(weights))]
        self.quantum = [self.MIN_QUANTUM * x / min(weights) for x in weights]
        self.active_set = set()

        # One FIFO queue for each flow_id
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
            print(f"Sent out packet {packet.id} from flow {packet.flow_id}")

        # todo: implement queue-level drr
        #       as an alternative to flow-level drr (curr. impl)
        self.deficit[packet.flow_id] -= packet.size

        if self.debug:
            print(f"Deficit reduced to {self.deficit[packet.flow_id]}")

        self.flow_queue_count[packet.flow_id] -= 1

        if self.flow_queue_count[packet.flow_id] == 0:
            self.deficit[packet.flow_id] = 0.0

        if packet.flow_id in self.byte_sizes:
            self.byte_sizes[packet.flow_id] -= packet.size
        else:
            raise ValueError(
                "Error: the packet to be sent has never been received.")

    def packet_in_service(self) -> Packet:
        """Returns the packet that is currently being sent to the downstream element.
        Used by a ServerMonitor.
        """
        return self.current_packet

    def byte_size(self, flow_id) -> int:
        """Returns the size of the queue for a particular flow_id, in bytes.
        Used by a ServerMonitor.
        """
        if flow_id in self.flow_queue_count:
            return self.byte_sizes[flow_id]
        else:
            return 0

    def size(self, flow_id) -> int:
        """Returns the size of the queue for a particular flow_id, in the
        number of packets. Used by a ServerMonitor.
        """
        if flow_id in self.flow_queue_count:
            return self.flow_queue_count[flow_id]
        else:
            return 0

    def run(self):
        """The generator function used in simulations."""
        while True:
            while sum(self.flow_queue_count) > 0:
                for flow_id, count in enumerate(self.flow_queue_count):
                    if count > 0:
                        self.deficit[flow_id] += self.quantum[flow_id]
                        if self.debug:
                            print(
                                f"Flow queue length: {self.flow_queue_count}",
                                f"Deficit counters: {self.deficit}")

                    while self.deficit[flow_id] > 0 and self.flow_queue_count[
                            flow_id] > 0:
                        if flow_id in self.head_of_line:
                            packet = self.head_of_line[flow_id]
                            del self.head_of_line[flow_id]
                        else:
                            if self.zero_downstream_buffer:
                                ds_store = self.downstream_stores[flow_id]
                                packet = yield ds_store.get()
                            else:
                                store = self.stores[flow_id]
                                packet = yield store.get()

                        assert flow_id == packet.flow_id

                        if packet.size <= self.deficit[flow_id]:
                            self.current_packet = packet
                            yield self.env.timeout(packet.size * 8.0 /
                                                   self.rate)

                            if self.zero_downstream_buffer:
                                if self.out_queue_id:
                                    packet.flow_id = self.out_queue_id
                                self.out.put(
                                    packet,
                                    upstream_update=self.update,
                                    upstream_store=self.stores[flow_id])
                            else:
                                if self.out_queue_id:
                                    packet.flow_id = self.out_queue_id
                                self.update(packet)
                                self.out.put(packet)

                            self.current_packet = None
                        else:
                            assert not flow_id in self.head_of_line
                            self.head_of_line[flow_id] = packet
                            break

            # No more packets in the scheduler to process at this time
            yield self.packets_available.get()

    def put(self, packet, upstream_update=None, upstream_store=None):
        """ Sends the packet 'pkt' to this element. """
        self.packets_received += 1
        self.byte_sizes[packet.flow_id] += packet.size

        flow_id = packet.flow_id

        if self.debug:
            print(f"Packet arrived at {self.env.now}, flow_id {flow_id},"
                  f"packet_id {packet.id}, deficit {self.deficit[flow_id]}"
                  f"Deficit counters: {self.deficit}")

        if not flow_id in self.stores:
            self.stores[flow_id] = simpy.Store(self.env)

            if self.zero_downstream_buffer:
                self.downstream_stores[flow_id] = simpy.Store(self.env)

        if sum(self.flow_queue_count) == 0:
            self.packets_available.put(True)

        self.flow_queue_count[flow_id] += 1

        if self.zero_buffer and upstream_update is not None and upstream_store is not None:
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update

        if self.zero_downstream_buffer:
            self.downstream_stores[flow_id].put(packet)

        return self.stores[flow_id].put(packet)
