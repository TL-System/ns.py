"""
Implements a network wire (cable) with a propagation delay. There is no need
to model a limited network capacity on this network cable, since such a
capacity limit can be modeled using an upstream port or server element in
the network.
"""

import random

import simpy


class Wire:
    """Implements a network wire (cable) that introduces a propagation delay.
    Set the "out" member variable to the entity to receive the packet.

    Parameters
    ----------
    env: simpy.Environment
        the simulation environment.
    delay_dist: function
        a no-parameter function that returns the successive propagation
        delays on this wire, in seconds. Delays overlap rather than serialize.
        This wire preserves arrival order: a later packet with a shorter delay
        waits for its predecessor instead of overtaking it.
    loss_dist: function
        a function that takes one optional parameter, which is the packet ID, and
        returns the loss rate.
    """

    def __init__(self, env, delay_dist, loss_dist=None, wire_id=0, debug=False):
        self.store = simpy.Store(env)
        self.delay_dist = delay_dist
        self.loss_dist = loss_dist
        self.env = env
        self.wire_id = wire_id
        self.out = None
        self.packets_rec = 0
        self.debug = debug
        self.action = env.process(self.run())

    def run(self):
        """Wait for packets and their entry-relative propagation deadlines in FIFO."""
        while True:
            packet, entry_time = yield self.store.get()

            if self.loss_dist is None or random.uniform(0, 1) >= self.loss_dist(
                packet_id=packet.packet_id
            ):
                # Propagation starts at this wire's entry, even while another
                # packet waits ahead. Keep that timestamp with the queue entry:
                # a shared packet can concurrently enter a different wire.
                queued_time = self.env.now - entry_time
                delay = self.delay_dist()

                # If queued time for this packet is greater than its propagation delay,
                # it implies that the previous packet had experienced a longer delay.
                # This wire's FIFO convention disallows overtaking, so deliver
                # to the next component immediately. A fixed-delay Days link
                # also preserves order, but Days has no delay-distribution wire.
                if queued_time < delay:
                    yield self.env.timeout(delay - queued_time)

                self.out.put(packet)

                if self.debug:
                    print(f"Left wire #{self.wire_id} at {self.env.now:.3f}: {packet}")
            else:
                if self.debug:
                    print(
                        f"Dropped on wire #{self.wire_id} at "
                        f"{self.env.now:.3f}: {packet}"
                    )

    def put(self, packet):
        """Sends a packet to this element."""
        self.packets_rec += 1
        if self.debug:
            print(f"Entered wire #{self.wire_id} at {self.env.now}: {packet}")

        packet.current_time = self.env.now
        return self.store.put((packet, self.env.now))
