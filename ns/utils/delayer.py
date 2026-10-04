"""FIFO packet delays in simulation seconds, preserving packet ownership."""

from math import isfinite
from random import uniform

import simpy


class Delayer:
    """Add a uniform delay without allowing later packets to overtake earlier ones.

    Parameters
        ----------
        env: simpy.Environment
            The simulation environment.
        max_delay:
            The maximum added delay in seconds, finite and nonnegative.
    """

    def __init__(self, env, max_delay):
        if not isfinite(max_delay) or max_delay < 0:
            raise ValueError("max_delay must be finite and nonnegative.")
        self.env = env
        self.max_delay = max_delay
        self.queue = simpy.Store(env)
        # Preserve the inspection attribute; Store owns the waiting entries and
        # wakes the process directly, without accumulating separate wake tokens.
        self.waiting_queue = self.queue.items
        self.out = None
        self.action = env.process(self.run())

    def run(self):
        """Wait for a packet, then for its arrival-based deadline if still ahead."""
        while True:
            packet, scheduled_time = yield self.queue.get()
            # If an earlier packet held up this one, its own deadline may have
            # passed. Deliver now to preserve FIFO without adding another delay.
            if self.env.now < scheduled_time:
                yield self.env.timeout(scheduled_time - self.env.now)
            self.out.put(packet)

    def put(self, packet):
        """Queue the original packet with its independently sampled deadline."""
        delay_time = uniform(0, self.max_delay)
        self.queue.put((packet, self.env.now + delay_time))


class StackDelayer:
    """Model sequential stack processing at a byte rate, preserving FIFO order.

    Parameters
        ----------
        env: simpy.Environment
            The simulation environment.
        speed: float
            Processing speed in bytes/second, positive; infinity adds no delay.
    """

    def __init__(self, env, speed):
        if not speed > 0:
            raise ValueError("speed must be positive.")
        self.env = env
        self.speed = speed
        self.queue = simpy.Store(env)
        self.waiting_queue = self.queue.items
        self.out = None
        self.action = env.process(self.run())

    def run(self):
        """Wait for each packet, then serialize its stack processing in seconds."""
        while True:
            packet = yield self.queue.get()
            # Both size and speed use bytes, unlike a link rate in bits/second;
            # there is no factor of eight for this processing delay.
            yield self.env.timeout(packet.size / self.speed)
            self.out.put(packet)

    def put(self, packet):
        """Queue the original packet for sequential processing."""
        self.queue.put(packet)
