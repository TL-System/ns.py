"""
This example shows how to simulate a switching port with exponential packet inter-arrival
times and exponentially distributed packet sizes. With a FIFO queueing discipline and no
limit on the queue sizes, such a system is equivalent to the well known M/M/1 queueing system,
which has nice analytical expressions for average queue size and waiting times.

In this example, we used the standard Python `functools` module to slightly ease the definition
of functions returning a random sample with a given parameter.

When we create the packet sink, we choose to turn off debug mode as we will have a great many
packets. We then use a PortMonitor to track the queue size.

The arrival times λ = 0.5 packets per second and the packet service rate μ = 1.25 packets
per second which gives a utilization ρ = 0.4. The theoretical mean queue size = 2/3 and the
mean waiting time is = 4/3.

The roughly exponential character of the resulting plot is a demonstration of Burke's theorem,
which is useful in the analysis of networks of queues.
"""
import os
import sys
import random
import functools
import simpy
import matplotlib.pyplot as plt

# To import modules from the parent directory
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

from packet.generator import PacketGenerator
from packet.sink import PacketSink
from port.port import SwitchPort
from port.monitor import PortMonitor


if __name__ == '__main__':
    # Set up arrival and packet size distributions
    # Using Python functools to create callable functions for random variates with fixed parameters.
    # each call to these will produce a new random value.
    adist = functools.partial(random.expovariate, 0.5)
    sdist = functools.partial(random.expovariate, 0.01)  # mean size 100 bytes
    samp_dist = functools.partial(random.expovariate, 1.0)
    port_rate = 1000.0

    env = simpy.Environment() # Create the SimPy environment

    # Create the packet generators and sink
    ps = PacketSink(env, debug=False, rec_arrivals=True)
    pg = PacketGenerator(env, "pg", adist, sdist)
    switch_port = SwitchPort(env, port_rate, qlimit=10000)

    # Using a PortMonitor to track queue sizes over time
    pm = PortMonitor(env, switch_port, samp_dist)

    # Wire packet generators, switch ports, and sinks together
    pg.out = switch_port
    switch_port.out = ps

    # Run it
    env.run(until=8000)

    print("Last 10 waits: "  + ", ".join(["{:.3f}".format(x) for x in ps.waits[-10:]]))
    print("Last 10 queue sizes: {}".format(pm.sizes[-10:]))
    print("Last 10 sink arrival times: " + ", ".join(["{:.3f}".format(x) for x in ps.arrivals[-10:]]))
    print("average wait = {:.3f}".format(sum(ps.waits) / len(ps.waits)))
    print("received: {}, dropped {}, sent {}".format(switch_port.packets_rec, switch_port.packets_drop, pg.packets_sent))
    print("loss rate: {}".format(float(switch_port.packets_drop) / switch_port.packets_rec))
    print("average system occupancy: {:.3f}".format(float(sum(pm.sizes)) / len(pm.sizes)))

    # fig, axis = plt.subplots()
    # axis.hist(ps.waits, bins=100, normed=True)
    # axis.set_title("Histogram for waiting times")
    # axis.set_xlabel("time")
    # axis.set_ylabel("normalized frequency of occurrence")
    # fig.savefig("WaitHistogram.png")
    # plt.show()
    # fig, axis = plt.subplots()
    # axis.hist(ps.waits, bins=100, normed=True)
    # axis.set_title("Histogram for System Occupation times")
    # axis.set_xlabel("number")
    # axis.set_ylabel("normalized frequency of occurrence")
    # fig.savefig("QueueHistogram.png")
    # plt.show()
    fig, axis = plt.subplots()
    axis.hist(ps.arrivals, bins=100, density=True)
    axis.set_title("Histogram for Sink Interarrival times")
    axis.set_xlabel("time")
    axis.set_ylabel("normalized frequency of occurrence")
    # fig.savefig("ArrivalHistogram.png")
    plt.show()
