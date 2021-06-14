"""
Models an ideal token bucket shaper.
"""
import simpy

class ShaperTokenBucket:
    """ The token bucket size should be greater than the size of the largest packet that 
    can occur on input. If this is not the case we always accumulate enough tokens to let
    the current packet pass based on the average rate. This may not be the behavior you desire.

    Parameters
    ----------
    env : simpy.Environment
        the simulation environment
    rate : float
        the token arrival rate in bits
    b_size : Number
        a token bucket size in bytes
    peak : Number or None for infinite peak
        the peak sending rate of the buffer (quickest time two packets could be sent)
    """
    def __init__(
        self, 
        env, 
        rate, 
        b_size, 
        peak=None, 
        zero_buffer=False,
        zero_downstream_buffer=False,
        debug=False):
        self.store = simpy.Store(env)
        self.rate = rate
        self.env = env
        self.out = None
        self.packets_rec = 0
        self.packets_sent = 0
        self.b_size = b_size
        self.peak = peak

        self.upstream_updates = {}
        self.upstream_stores = {}
        self.zero_buffer = zero_buffer
        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_stores = simpy.Store(env)

        self.current_bucket = b_size  # Current size of the bucket in bytes
        self.update_time = 0.0  # Last time the bucket was updated
        self.debug = debug
        self.busy = 0  # Used to track if a packet is currently being sent ?
        self.action = env.process(self.run())  # starts the run() method as a SimPy process

    def update(self, packet):
        if self.zero_buffer:
            self.upstream_stores[packet].get()
            del self.upstream_stores[packet]
            self.upstream_updates[packet](packet)
            del self.upstream_updates[packet]
        
        if self.debug:
            print(f"Sent packet {packet.id} from flow {packet.flow_id} with color {packet.color}")

    def run(self):
        while True:
            if self.zero_downstream_buffer:
                packet = yield self.downstream_stores.get()
            else:
                packet = yield self.store.get()
                self.update(packet)
            now = self.env.now

            self.current_bucket = min(
                self.b_size, self.current_bucket + self.rate * (
                    now - self.update_time) / 8.0)
            self.update_time = now

            if packet.size > self.current_bucket:
                yield self.env.timeout(
                    (packet.size -self.current_bucket)*8.0/self.rate)
                self.current_bucket = 0.0
                self.update_time = self.env.now
            else:
                self.current_bucket -= packet.size
                self.update_time = self.env.now

            if not self.peak:
                if self.zero_downstream_buffer:
                    self.out.put(
                        packet,
                        upstream_update=self.update,
                        upstream_store=self.store)
                else:
                    self.out.put(packet)
            else:
                yield self.env.timeout(packet.size*8.0/self.rate)
                if self.zero_downstream_buffer:
                    self.out.put(
                        packet,
                        upstream_update=self.update,
                        upstream_store=self.store)
                else:
                    self.out.put(packet)

            self.packets_sent +=1
            if self.debug:
                print(packet)


    def put(self, packet, upstream_update=None, upstream_store=None):
        self.packets_rec +=1
        if self.zero_buffer and upstream_update is not None and upstream_store is not None:
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update
        
        if self.zero_downstream_buffer:
            self.downstream_stores.put(packet)

        return self.store.put(packet)

# todo: two rate token bucket