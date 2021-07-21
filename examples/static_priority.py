"""
A basic example that connects two packet generators to a network wire with
a propagation delay distribution, and then to a packet sink.
"""

import simpy

from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.scheduler.sp import SPServer


def arrival_1():
    """ Packets arrive with a constant interval of 1.5 seconds. """
    return 1.5


def arrival_2():
    """ Packets arrive with a constant interval of 2.0 seconds. """
    return 2.0


def packet_size():
    return 100


env = simpy.Environment()
sp1 = SPServer(env,
               100, {
                   0: 1,
                   1: 10
               },
               zero_downstream_buffer=True,
               debug=True)
sp2 = SPServer(env, 100, {0: 50, 1: 100}, zero_buffer=True, debug=True)
ps = PacketSink(env, rec_flow_ids=False, debug=True)

pg1 = DistPacketGenerator(env, "flow_1", arrival_1, packet_size, flow_id=0)
pg2 = DistPacketGenerator(env, "flow_2", arrival_2, packet_size, flow_id=1)

pg1.out = sp1
pg2.out = sp1
sp1.out = sp2
sp2.out = ps

env.run(until=20)
