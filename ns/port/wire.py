import simpy


class Wire:
    def __init__(self, env, delay_dist, wire_id=0, debug=False) -> None:
        self.store = simpy.Store(env)
        self.delay_dist = delay_dist
        self.env = env
        self.id = wire_id
        self.out = None
        self.packets_received = 0
        self.debug = debug
        self.action = env.process(self.run())

    def run(self):
        """The generator function used in simulations."""
        while True:
            packet = yield self.store.get()

            queued_time = self.env.now - packet.current_time
            delay = self.delay_dist()

            if queued_time < delay:
                yield self.env.timeout(delay - queued_time)

            if self.debug:
                print(f"Left wire {self.id} at {self.env.now}: {packet}")

    def put(self, packet):
        """ Sends the packet 'pkt' to this element. """
        self.packets_received += 1
        if self.debug:
            print(f"Entered wire {self.id} at {self.env.now}: {packet}")
        packet.current_time = self.env.now
        return self.store.put(packet)
