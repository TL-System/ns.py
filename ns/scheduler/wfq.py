"""
Implements a Weighted Fair Queueing (WFQ) server.
"""
from collections import defaultdict as dd

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
        This can be either a list or a dictionary. If it is a list, it uses the flow_id
        as its index to look for the flow's corresponding weight. If it is a dictionary,
        it contains (flow_id -> weight) pairs for each possible flow_id.
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
                 weights,
                 zero_buffer=False,
                 zero_downstream_buffer=False,
                 debug=False) -> None:
        self.env = env
        self.rate = rate
        self.weights = weights

        if isinstance(weights, list):
            # Initialize all the finish time values
            self.finish_times = [0.0 for __ in range(len(weights))]
            # Keep track of the number of packets from each flow in the queue
            self.flow_queue_count = [0 for __ in range(len(weights))]
        elif isinstance(weights, dict):
            self.finish_times = {key: 0.0 for (key, __) in weights.items()}
            self.flow_queue_count = {key: 0 for (key, __) in weights.items()}
        else:
            raise ValueError('Weights must be either a list or a dictionary.')

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

    def packet_in_service(self) -> Packet:
        """
        Returns the packet that is currently being sent to the downstream element.
        Used by a ServerMonitor.
        """
        return self.current_packet

    def byte_size(self, flow_id) -> int:
        """
        Returns the size of the queue for a particular flow_id, in bytes.
        Used by a ServerMonitor.
        """
        if flow_id in self.byte_sizes:
            return self.byte_sizes[flow_id]

        return 0

    def size(self, flow_id) -> int:
        """
        Returns the size of the queue for a particular flow_id, in the
        number of packets. Used by a ServerMonitor.
        """
        return self.flow_queue_count[flow_id]

    def all_flows(self) -> list:
        """
        Returns a list containing all the flow IDs.
        """
        return self.byte_sizes.keys()

    def update(self, packet):
        """The packet has just been retrieved from this element's own buffer, so
        update internal housekeeping states accordingly.
        """
        if self.zero_buffer:
            self.upstream_stores[packet].get()
            del self.upstream_stores[packet]
            self.upstream_updates[packet](packet)
            del self.upstream_updates[packet]

        self.last_update = self.env.now
        flow_id = packet.flow_id

        self.flow_queue_count[flow_id] -= 1
        if self.flow_queue_count[flow_id] == 0:
            self.active_set.remove(flow_id)

        if len(self.active_set) == 0:
            self.vtime = 0.0
            for i in range(len(self.finish_times)):
                self.finish_times[i] = 0.0

        if self.debug:
            print(f"Sent Packet {packet.packet_id} from flow {flow_id}")

        if flow_id in self.byte_sizes:
            self.byte_sizes[flow_id] -= packet.size
        else:
            raise ValueError("Error: the packet is from an unrecorded flow.")

    def run(self):
        """The generator function used in simulations."""
        while True:
            if self.zero_downstream_buffer:
                packet = yield self.downstream_store.get()
                self.current_packet = packet
                yield self.env.timeout(packet.size * 8.0 / self.rate)
                self.out.put(packet,
                             upstream_update=self.update,
                             upstream_store=self.store)
                self.current_packet = None
            else:
                packet = yield self.store.get()
                self.update(packet)

                self.current_packet = packet
                yield self.env.timeout(packet.size * 8.0 / self.rate)
                self.out.put(packet)
                self.current_packet = None

    def put(self, packet, upstream_update=None, upstream_store=None):
        """ Sends a packet to this element. """
        self.packets_received += 1
        self.byte_sizes[packet.flow_id] += packet.size
        now = self.env.now
        flow_id = packet.flow_id
        self.flow_queue_count[flow_id] += 1
        self.active_set.add(flow_id)

        weight_sum = 0.0
        for i in self.active_set:
            weight_sum += self.weights[i]

        self.vtime += (now - self.last_update) / weight_sum
        self.finish_times[flow_id] = max(
            self.finish_times[flow_id],
            self.vtime) + packet.size * 8.0 / self.weights[flow_id]

        if self.debug:
            print(
                f"Packet arrived at {self.env.now}, with flow_id {flow_id}, "
                f"packet_id {packet.packet_id}, finish_time {self.finish_times[flow_id]}"
            )

        self.last_update = now

        if self.zero_buffer and upstream_update is not None and upstream_store is not None:
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update

        if self.zero_downstream_buffer:
            self.downstream_store.put((self.finish_times[flow_id], packet))

        return self.store.put((self.finish_times[flow_id], packet))
