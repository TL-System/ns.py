"""
Implements a delayer that calls arbitrary delay within [0,D] without changing the order
of packets arrived.
"""
from copy import copy
from random import uniform
from turtle import delay
import simpy

class Delayer:
    """ 
    Parameters
        ----------
        env: simpy.Environment
            The simulation environment.
        timer_id: int
            The id of this timer, used as a parameter when the timeout
            callback function is called.
        timeout_callback:
            The callback function that runs when the timer expires.
        timeout: float
            The timeout value.
    """
    def __init__(self, env, max_delay):
        self.env = env
        self.max_delay = max_delay
        # self.delay_time = uniform(0, self.max_delay)
        self.delay_time = max_delay
        self.waiting_queue = []
        self.queue = simpy.Store(env)
        self.out = None
        self.action = env.process(self.run())

    def run(self):
        """ The generator function used in simulations. """
        while True:
            if len(self.waiting_queue)==0:
                yield self.queue.get()
            else:
                packet, delay_time = self.waiting_queue.pop(0)
                if self.env.now < delay_time:
                    yield self.env.timeout(delay_time-self.env.now)
                self.out.put(packet)

    def put(self,packet):
        temp_pkt = copy(packet)
        self.waiting_queue.append((temp_pkt, self.env.now + self.delay_time))
        self.queue.put(True)

class StackDelayer:
    """ 
    Parameters
        ----------
        env: simpy.Environment
            The simulation environment.
        timer_id: int
            The id of this timer, used as a parameter when the timeout
            callback function is called.
        timeout_callback:
            The callback function that runs when the timer expires.
        timeout: float
            The timeout value.
    """
    def __init__(self, env, speed):
        self.env = env
        self.waiting_queue = []
        self.speed = speed
        self.queue = simpy.Store(env)
        self.out = None
        self.action = env.process(self.run())

    def run(self):
        """ The generator function used in simulations. """
        while True:
            if len(self.waiting_queue)==0:
                yield self.queue.get()
            else:
                packet = self.waiting_queue.pop(0)
                delay_time = packet.size / self.speed
                yield self.env.timeout(delay_time)
                self.out.put(packet)
    
    def put(self,packet):
        temp_pkt = copy(packet)
        self.waiting_queue.append(temp_pkt)
        self.queue.put(True)
