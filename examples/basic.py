"""
A basic example that connects two packet generators to one packet sink.
"""
from random import expovariate
import simpy

from ns.packet.generator import PacketGenerator
from ns.packet.sink import PacketSink


def constArrival():  # Constant arrival distribution for generator 1
    return 1.5


def constArrival2():
    return 2.0


def distSize():
    return expovariate(0.01)


env = simpy.Environment()  # Create the SimPy environment

# Create the packet generators and sink
ps = PacketSink(env, debug=True)  # debugging enable for simple output
pg = PacketGenerator(env, "pg1", constArrival, distSize)
pg2 = PacketGenerator(env, "pg2", constArrival2, distSize)

# Wire packet generators and sink together
pg.out = ps
pg2.out = ps

env.run(until=20)
