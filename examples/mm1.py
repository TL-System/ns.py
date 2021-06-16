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
import random
import functools
import simpy
import matplotlib.pyplot as plt

from ns.packet.dist_generator import PacketDistGenerator
from ns.packet.sink import PacketSink
from ns.port.port import Port
from ns.port.monitor import PortMonitor

adist = functools.partial(random.expovariate, 0.5)
sdist = functools.partial(random.expovariate, 0.01)  # a mean size of 100 bytes
samp_dist = functools.partial(random.expovariate, 1.0)
port_rate = 1000.0

env = simpy.Environment()

ps = PacketSink(env, debug=False, rec_arrivals=True)
pg = PacketDistGenerator(env, "pg", adist, sdist, flow_id=0)
port = Port(env, port_rate, qlimit=10000)

# Using a PortMonitor to track queue sizes over time
pm = PortMonitor(env, port, samp_dist)

# Wire packet generators, switch ports, and sinks together
pg.out = port
port.out = ps

env.run(until=8000)

print("Last 10 waits: " +
      ", ".join(["{:.3f}".format(x) for x in ps.waits[0][-10:]]))
print("Last 10 queue sizes: {}".format(pm.sizes[-10:]))
print("Last 10 sink arrival times: " +
      ", ".join(["{:.3f}".format(x) for x in ps.arrivals[0][-10:]]))
print("average wait = {:.3f}".format(sum(ps.waits[0]) / len(ps.waits[0])))
print("received: {}, dropped {}, sent {}".format(port.packets_received,
                                                 port.packets_dropped,
                                                 pg.packets_sent))
print("loss rate: {}".format(
    float(port.packets_dropped) / port.packets_received))
print("average system occupancy: {:.3f}".format(
    float(sum(pm.sizes)) / len(pm.sizes)))

fig, axis = plt.subplots()
axis.hist(ps.waits[0], bins=100)
axis.set_title("Histogram for waiting times")
axis.set_xlabel("time")
axis.set_ylabel("normalized frequency of occurrence")
fig.savefig("WaitHistogram.png")
plt.show()
fig, axis = plt.subplots()
axis.hist(ps.waits[0], bins=100)
axis.set_title("Histogram for system occupation times")
axis.set_xlabel("number")
axis.set_ylabel("normalized frequency of occurrence")
fig.savefig("QueueHistogram.png")
plt.show()
fig, axis = plt.subplots()
axis.hist(ps.arrivals[0], bins=100, density=True)
axis.set_title("Histogram for sink inter-arrival times")
axis.set_xlabel("time")
axis.set_ylabel("normalized frequency of occurrence")
fig.savefig("ArrivalHistogram.png")
plt.show()
