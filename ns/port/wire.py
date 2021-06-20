"""
Implements a network wire (cable) with a propagation delay. There is no need
to model a limited network capacity on this network cable, since such a
capacity limit can be modeled using an upstream port or server element in
the network.
"""
import simpy


class Wire:
    """ Implements a network wire (cable) that introduces a propagation delay.
        Set the "out" member variable to the entity to receive the packet.

        Parameters
        ----------
        env: simpy.Environment
            the simulation environment
        delay: float
            a no-parameter function that returns the successive propagation
            delays on this wire
    """
    def __init__(self, env, delay_dist, wire_id=0, debug=False):
        self.store = simpy.Store(env)
        self.delay_dist = delay_dist
        self.env = env
        self.wire_id = wire_id
        self.out = None
        self.packets_rec = 0
        self.debug = debug
        self.action = env.process(
            self.run())  # starts the run() method as a SimPy process

    def run(self):
        """The generator function used in simulations."""
        while True:
            packet = yield self.store.get()

            # The amount of time for this packet to stay in my store
            queued_time = self.env.now - packet.current_time
            delay = self.delay_dist()

            # If queued time for this packet is greater than its propagation delay,
            # it implies that the previous packet had experienced a longer delay.
            # Since out-of-order delivery is not supported in simulation, deliver
            # to the next component immediately.
            if queued_time < delay:
                yield self.env.timeout(delay - queued_time)

            if self.debug:
                print("Left wire #{} at {:.3f}: {}".format(
                    self.wire_id, self.env.now, packet))

            self.out.put(packet)

    def put(self, packet):
        """ Sends a packet to this element. """
        self.packets_rec += 1
        if self.debug:
            print(f"Entered wire #{self.wire_id} at {self.env.now}: {packet}")

        packet.current_time = self.env.now
        return self.store.put(packet)
