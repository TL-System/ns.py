"""
Implements a delayer that adds arbitrary delay within [0, D] without changing the order
of packets arrived.
"""
from copy import copy
from random import uniform

import simpy


class Delayer:
    """
    Parameters
        ----------
        env: simpy.Environment
            The simulation environment.
        max_delay:
            The maximum amount of delay.
    """

    def __init__(self, env, max_delay):
        self.env = env
        self.max_delay = max_delay
        self.waiting_queue = []
        self.queue = simpy.Store(env)
        self.out = None
        self.action = env.process(self.run())

    def run(self):
        """The generator function used in simulations."""
        while True:
            if len(self.waiting_queue) == 0:
                yield self.queue.get()
            else:
                packet, scheduled_time = self.waiting_queue.pop(0)
                if self.env.now < scheduled_time:
                    yield self.env.timeout(scheduled_time - self.env.now)
                self.out.put(packet)

    def put(self, packet):
        """Sends a packet to this element."""
        new_packet = copy(packet)
        delay_time = uniform(0, self.max_delay)
        self.waiting_queue.append((new_packet, self.env.now + delay_time))
        self.queue.put(True)


class StackDelayer:
    """
    Parameters
        ----------
        env: simpy.Environment
            The simulation environment.
    """

    def __init__(self, env, speed):
        self.env = env
        self.waiting_queue = []
        self.speed = speed
        self.queue = simpy.Store(env)
        self.out = None
        self.action = env.process(self.run())

    def run(self):
        """The generator function used in simulations."""
        while True:
            if len(self.waiting_queue) == 0:
                yield self.queue.get()
            else:
                packet = self.waiting_queue.pop(0)
                delay_time = packet.size / self.speed
                yield self.env.timeout(delay_time)
                self.out.put(packet)

    def put(self, packet):
        """Sends a packet to this element."""
        new_packet = copy(packet)
        self.waiting_queue.append(new_packet)
        self.queue.put(True)
