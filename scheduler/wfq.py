"""
Models a WFQ/PGPS server.
"""
import flow
from utils import stampedstore
from packet.packet import Packet

class WFQServer:
    """
    Parameters
    ----------
    env: simpy.Environment
        the simulation environment
    rate: float
        the bit rate of the port
    weights: A list of weights for each possible packet flow_id. We assume a simple assignment
        of flow ids to weights, i.e., flow_id = 0 corresponds to weights[0], etc.
    """
    def __init__(
        self, 
        env, 
        rate, 
        weights, 
        zero_buffer=False,
        zero_downstream_buffer=False,
        debug=False):
        self.env = env
        self.rate = rate
        self.weights = weights
        self.F_times = [0.0 for i in range(len(weights))]  # Initialize all the finish time variables

        # We keep track of the number of packets from each flow in the queue
        self.flow_queue_count = [0 for i in range(len(weights))]
        self.active_set = set()
        self.vtime = 0.0
        self.out = None
        self.packets_rec = 0
        self.packets_dropped = 0
        self.debug = debug

        self.current_packet = None

        self.byte_sizes = {}

        self.upstream_updates = {}
        self.upstream_stores = {}
        self.zero_buffer = zero_buffer
        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_store = stampedstore.StampedStore(env)
        
        self.store = stampedstore.StampedStore(env)
        self.action = env.process(self.run())  # starts the run() method as a SimPy process
        self.last_update = 0.0

    def packet_in_service(self) -> Packet:
        return self.current_packet

    def byte_size(self, flow_id) -> int:
        if flow_id in self.byte_sizes:
            return self.byte_sizes[flow_id]
        else:
            return 0

    def size(self, flow_id) -> int:
        return self.flow_queue_count[flow_id]

    def update(self, packet):
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
            for i in range(len(self.F_times)):
                self.F_times[i] = 0.0
        
        if self.debug:
            print(f"Sent Packet {packet.id} from flow {flow_id}")

        if flow_id in self.byte_sizes:
            self.byte_sizes[flow_id] -= packet.size
        else:
            assert "Error: packet from unrecorded flow"
    
    def run(self):
        while True:
            if self.zero_downstream_buffer:
                packet = yield self.downstream_store.get()
                self.current_packet = packet
                yield self.env.timeout(packet.size*8.0/self.rate)
                self.out.put(
                    packet,
                    upstream_update=self.update,
                    upstream_store=self.store
                )
                self.current_packet = None
            else:
                packet = yield self.store.get()
                self.update(packet)

                self.current_packet = packet
                yield self.env.timeout(packet.size*8.0/self.rate)
                self.out.put(packet)
                self.current_packet = None

    def put(self, packet, upstream_update=None, upstream_store=None):
        self.packets_rec +=1
        # todo: simplify this with defaultdict
        if packet.flow_id in self.byte_sizes:
            self.byte_sizes[packet.flow_id] += packet.size
        else:
            self.byte_sizes[packet.flow_id] = packet.size

        now = self.env.now
        flow_id = packet.flow_id
        self.flow_queue_count[flow_id] +=1
        self.active_set.add(flow_id)

        weight_sum = 0.0
        for i in self.active_set:
            weight_sum += self.weights[i]

        self.vtime += (now-self.last_update)/weight_sum
        self.F_times[flow_id] = max(
            self.F_times[flow_id],
            self.vtime) + packet.size*8.0/self.weights[flow_id]
        
        if self.debug:
            print(f"Packet arrived at {self.env.now}, flow_id {flow_id}, packet_id {packet.id}, F_time {self.F_times[flow_id]}")

        self.last_update = now

        if self.zero_buffer and upstream_update is not None and upstream_store is not None:
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update
        
        if self.zero_downstream_buffer:
            self.downstream_store.put((self.F_times[flow_id], packet))

        return self.store.put((self.F_times[flow_id], packet))

        