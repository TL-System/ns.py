"""
A basic example that connects two packet generators to a network wire with
a propagation delay distribution, and then to a packet sink.
"""
from functools import partial
import random
from random import expovariate

import simpy
from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.port.wire import Wire


def arrival_1():
    """ Packets arrive with a constant interval of 1.5 seconds. """
    return 1.5


def arrival_2():
    """ Packets arrive with a constant interval of 2.0 seconds. """
    return 2.0


def delay_dist():
    return 0.1


def packet_size():
    return int(expovariate(0.01))


env = simpy.Environment()

ps = PacketSink(env, rec_flow_ids=False, debug=True)

pg1 = DistPacketGenerator(env, "flow_1", arrival_1, packet_size, flow_id=0)
pg2 = DistPacketGenerator(env, "flow_2", arrival_2, packet_size, flow_id=1)

wire1 = Wire(env, partial(random.gauss, 0.1, 0.02), wire_id=1, debug=True)
wire2 = Wire(env, delay_dist, wire_id=2, debug=True)

pg1.out = wire1
pg2.out = wire2
wire1.out = ps
wire2.out = ps

env.run(until=100)

print("Flow 1 packet delays: " +
      ", ".join(["{:.3f}".format(x) for x in ps.waits['flow_1']]))
print("Flow 2 packet delays: " +
      ", ".join(["{:.3f}".format(x) for x in ps.waits['flow_2']]))

print("Packet arrival times in flow 1: " +
      ", ".join(["{:.3f}".format(x) for x in ps.arrivals['flow_1']]))

print("Packet arrival times in flow 2: " +
      ", ".join(["{:.3f}".format(x) for x in ps.arrivals['flow_2']]))
