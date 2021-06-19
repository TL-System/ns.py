"""
Implements a token bucket shaper.
"""
import simpy


class TokenBucketShaper:
    """ The token bucket size should be greater than the size of the largest packet that
    can occur on input. If this is not the case we always accumulate enough tokens to let
    the current packet pass based on the average rate. This may not be the behavior you desire.

    Parameters
    ----------
    env: simpy.Environment
        The simulation environment.
    rate: int
        The token arrival rate in bits.
    bucket_size: int
        The token bucket size in bytes.
    peak: int (or None for an infinite peak sending rate)
        The peak sending rate in bits of the buffer (quickest time two packets could be sent).
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
                 bucket_size,
                 peak=None,
                 zero_buffer=False,
                 zero_downstream_buffer=False,
                 debug=False):
        self.store = simpy.Store(env)
        self.env = env
        self.rate = rate
        self.out = None
        self.packets_received = 0
        self.packets_sent = 0
        self.bucket_size = bucket_size
        self.peak = peak

        self.upstream_updates = {}
        self.upstream_stores = {}
        self.zero_buffer = zero_buffer
        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_stores = simpy.Store(env)

        self.current_bucket = bucket_size  # Current size of the bucket in bytes
        self.update_time = 0.0  # Last time the bucket was updated
        self.debug = debug
        self.busy = 0  # Used to track if a packet is currently being sent
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
                f"Sent packet {packet.packet_id} from flow {packet.flow_id}.")

    def run(self):
        """The generator function used in simulations."""
        while True:
            if self.zero_downstream_buffer:
                packet = yield self.downstream_stores.get()
            else:
                packet = yield self.store.get()
                self.update(packet)

            now = self.env.now

            # Add tokens to the bucket based on the current time
            self.current_bucket = min(
                self.bucket_size, self.current_bucket + self.rate *
                (now - self.update_time) / 8.0)
            self.update_time = now

            # Check if there are a sufficient number of tokens to allow the packet
            # to be sent; if not, we will then wait to accumulate enough tokens to
            # allow this packet to be sent regardless of the bucket size.
            if packet.size > self.current_bucket:  # needs to wait for the bucket to fill
                yield self.env.timeout(
                    (packet.size - self.current_bucket) * 8.0 / self.rate)
                self.current_bucket = 0.0
                self.update_time = self.env.now
            else:
                self.current_bucket -= packet.size
                self.update_time = self.env.now

            # Sending the packet now
            if self.peak is None:  # infinite peak rate
                if self.zero_downstream_buffer:
                    self.out.put(packet,
                                 upstream_update=self.update,
                                 upstream_store=self.store)
                else:
                    self.out.put(packet)
            else:
                yield self.env.timeout(packet.size * 8.0 / self.peak)
                if self.zero_downstream_buffer:
                    self.out.put(packet,
                                 upstream_update=self.update,
                                 upstream_store=self.store)
                else:
                    self.out.put(packet)

            self.packets_sent += 1
            if self.debug:
                print(
                    f"Sent packet {packet.packet_id} from flow {packet.flow_id}."
                )

    def put(self, packet, upstream_update=None, upstream_store=None):
        """ Sends a packet to this element. """
        self.packets_received += 1
        if self.zero_buffer and upstream_update is not None and upstream_store is not None:
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update

        if self.zero_downstream_buffer:
            self.downstream_stores.put(packet)

        return self.store.put(packet)
