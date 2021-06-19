"""
Implments a two-rate token bucket shaper, with a bucket for committed information rate (CIR) and
another for the peak information rate (PIR).
"""
import simpy


class TwoRateTokenBucketShaper:
    """ The token bucket size should be greater than the size of the largest packet that
    can occur on input. If this is not the case we always accumulate enough tokens to let
    the current packet pass based on the average rate. This may not be the behavior you desire.

    Parameters
    ----------
    env: simpy.Environment
        The simulation environment.
    cir: int
        The Committed Information Rate (CIR) in bits.
    cbs: int
        The Committed Burst Size (CBS) in bytes.
    pir: int
        The Peak Information Rate (CIR) in bits.
    pbs: int
        The Peak Burst Size (PBS) in bytes.
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
                 cir,
                 cbs,
                 pir=None,
                 pbs=None,
                 zero_buffer=False,
                 zero_downstream_buffer=False,
                 debug=False):
        self.store = simpy.Store(env)
        self.env = env
        self.out = None
        self.cir = cir
        self.cbs = cbs
        self.pir = pir
        self.pbs = pbs
        self.packets_received = 0
        self.packets_sent = 0

        self.upstream_updates = {}
        self.upstream_stores = {}
        self.zero_buffer = zero_buffer
        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_stores = simpy.Store(env)

        self.current_bucket_commit = cbs  # Current size of the committed bucket in bytes
        self.current_bucket_peak = pbs  # Current size of the peak bucket in bytes
        self.update_time = 0.0  # Last time the bucket was updated
        self.debug = debug
        self.busy = 0  # Used to track if a packet is currently being sent
        self.action = env.process(self.run())

    def update(self, packet):
        """The packet has just been retrieved from this element's own buffer, so
        update internal housekeeping states accordingly."""
        # With no local buffers, this element needs to pull the packet from upstream
        if self.zero_buffer:
            # For each packet, remove it from its own upstream's store
            self.upstream_stores[packet].get()
            del self.upstream_stores[packet]
            self.upstream_updates[packet](packet)
            del self.upstream_updates[packet]

    def run(self):
        """The generator function used in simulations."""
        while True:
            if self.zero_downstream_buffer:
                packet = yield self.downstream_stores.get()
            else:
                packet = yield self.store.get()
                self.update(packet)
            now = self.env.now

            #  Add tokens to bucket based on current time, both C & B buckets need to add
            self.current_bucket_commit = min(
                self.cbs, self.current_bucket_commit + self.cir *
                (now - self.update_time) / 8.0)
            if self.pir:
                self.current_bucket_peak = min(
                    self.pbs, self.current_bucket_peak + self.pir *
                    (now - self.update_time) / 8.0)
            self.update_time = now

            # Check if there are a sufficient number of tokens to allow the packet
            # to be sent; if not, we will then wait to accumulate enough tokens to
            # allow this packet to be sent regardless of the bucket size.
            if self.pir:
                # first compare with peak bucket
                if packet.size > self.current_bucket_peak:
                    yield self.env.timeout(
                        (packet.size - self.current_bucket_peak) * 8.0 /
                        self.pir)
                    self.current_bucket_peak = 0.0
                    packet.color = 'red'
                    self.update_time = self.env.now
                # then compare with committed bucket: > committed bucket and < peak bucket
                elif packet.size > self.current_bucket_commit:
                    self.current_bucket_peak -= packet.size
                    self.current_bucket_commit = 0.0
                    packet.color = 'yellow'
                    self.update_time = self.env.now
                # the packet size < committed bucket
                else:
                    self.current_bucket_commit -= packet.size
                    self.current_bucket_peak -= packet.size
                    packet.color = 'green'
                    self.update_time = self.env.now

            else:  # use CIR or use CIR as PIR
                if packet.size > self.current_bucket_commit:
                    yield self.env.timeout(
                        (packet.size - self.current_bucket_commit) * 8.0 /
                        self.cir)
                    self.current_bucket_commit = 0.0
                    packet.color = 'yellow'
                    self.update_time = self.env.now
                else:
                    self.current_bucket_commit -= packet.size
                    packet.color = 'green'
                    self.update_time = self.env.now

            # Sending the packet now
            if self.zero_downstream_buffer:
                self.out.put(packet,
                             upstream_update=self.update,
                             upstream_store=self.store)
            else:
                self.out.put(packet)

            self.packets_sent += 1
            if self.debug:
                print(
                    f"Sent out packet with id {packet.packet_id} "
                    f"belonging to flow {packet.flow_id} with color {packet.color}."
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
