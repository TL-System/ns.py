import os
import sys
import simpy

# To import modules from the parent directory
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

from packet.generator import PacketGenerator
from packet.sink import PacketSink
from switch.switch import SwitchPort


def constArrival():
    return 1.5    # time interval

def constSize():
    return 100.0  # bytes

env = simpy.Environment()  # Create the SimPy environment
ps = PacketSink(env, debug=True) # debug: every packet arrival is printed
pg = PacketGenerator(env, "SJSU", constArrival, constSize)

switch_port = SwitchPort(env, rate=200.0, qlimit=300)

# Wire packet generators and sinks together
pg.out = switch_port
switch_port.out = ps

env.run(until=40)

print("waits: {}".format(ps.waits))
print("received: {}, dropped {}, sent {}".format(ps.packets_rec, switch_port.packets_drop, pg.packets_sent))
