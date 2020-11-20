"""
In this example, we have a packet generator connected to a switch port which is then
connected to a packet sink. We see that packets will be generated with a constant interarrival
time of 1.5 seconds, and will have a constant size of 100 bytes. This gives an average arrival
rate of about 533.3 bps. We then create our switch port but it only has a line rate of 200 bps
(note that the unit is bits per second), and a queue limit of 300 bytes. Hence it hould be pushed
into dropping packets quickly.

We see from the output that, if we simulate to 20 seconds, only four packets are received at the
sink by the time the simulation is stopped (the simulation can be resumed with just another call
to the run() method). In addition to the debugging output for each packet received at the sink,
we have the information from the packet sink and switch port. Note how the first 100 byte packet
incurs a delay of 4 seconds (due to the 200 bps line rate) and also the received and dropped packet
counts.
"""
import os
import sys
import simpy

# To import modules from the parent directory
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

from packet.generator import PacketGenerator
from packet.sink import PacketSink
from port.port import SwitchPort

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

env.run(until=20)

print("waits: {}".format(ps.waits))
print("received: {}, dropped {}, sent {}".format(ps.packets_rec, switch_port.packets_drop, pg.packets_sent))
