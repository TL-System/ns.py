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
import simpy

from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.port.port import Port


def packet_arrival():
    return 1.5


def packet_size():
    return 100.0


env = simpy.Environment()
ps = PacketSink(env, debug=True)
pg = DistPacketGenerator(env, "pg", packet_arrival, packet_size, flow_id=0)
port = Port(env, rate=200.0, qlimit=300)

pg.out = port
port.out = ps

env.run(until=20)

print("waits: {}".format(ps.waits[0]))
print("received: {}, dropped {}, sent {}".format(ps.packets_received[0],
                                                 port.packets_dropped,
                                                 pg.packets_sent))
