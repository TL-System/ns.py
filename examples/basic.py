"""
A basic example that connects two packet generators to one packet sink.
"""
from random import expovariate
import simpy

from ns.packet.dist_generator import PacketDistGenerator
from ns.packet.sink import PacketSink


def arrival_1():
    """ Packets arrive with a constant interval of 1.5 seconds. """
    return 1.5


def arrival_2():
    """ Packets arrive with a constant interval of 2 seconds. """
    return 2.0


def packet_size():
    return int(expovariate(0.01))


env = simpy.Environment()

pg1 = PacketDistGenerator(env, "flow_0", arrival_1, packet_size, flow_id=0)
pg2 = PacketDistGenerator(env, "flow_1", arrival_2, packet_size, flow_id=1)

# Debugging mode is enabled to print more information
ps = PacketSink(env, debug=True)

pg1.out = ps
pg2.out = ps

env.run(until=20)

print("Packet arrival times for flow 0:")
print(ps.arrivals[0])

print("Packet arrival times for flow 1:")
print(ps.arrivals[1])
