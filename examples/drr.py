"""
An example of using the Deficit Round Robin (DRR) server.
"""

import simpy
import matplotlib.pyplot as plt

from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.utils.splitter import Splitter
from ns.scheduler.drr import DRRServer


def packet_arrival():
    return 1.75


def const_size():
    return 1000.0


env = simpy.Environment()
pg1 = DistPacketGenerator(
    env, "flow_0", packet_arrival, const_size, initial_delay=0.0, finish=50, flow_id=0
)
pg2 = DistPacketGenerator(
    env, "flow_1", packet_arrival, const_size, initial_delay=10.0, finish=50, flow_id=1
)
ps = PacketSink(env)
sink_1 = PacketSink(env)
sink_2 = PacketSink(env)

source_rate = 8.0 * const_size() / packet_arrival()
drr_server = DRRServer(env, source_rate, [1, 2], debug=True)
splitter_1 = Splitter()
splitter_2 = Splitter()

pg1.out = splitter_1
pg2.out = splitter_2

splitter_1.out1 = drr_server
splitter_1.out2 = sink_1
splitter_2.out1 = drr_server
splitter_2.out2 = sink_2

drr_server.out = ps

env.run(until=100)

print("At the packet sink, packet arrival times for flow 0 are:")
print(ps.arrivals[0])

print("At the packet sink, packet arrival times for flow 1 are:")
print(ps.arrivals[1])

fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, sharex=True)
ax1.vlines(sink_1.arrivals[0], 0.0, 1.0, colors="g", linewidth=2.0, label="Flow 0")
ax1.vlines(sink_2.arrivals[1], 0.0, 0.7, colors="r", linewidth=2.0, label="Flow 1")
ax1.set_title("Arrival times at DRR switch")
ax1.set_ylim([0, 1.5])
ax1.set_xlim([0, max(ps.arrivals[0]) + 10])
ax1.grid(True)
ax1.legend()

ax2.vlines(ps.arrivals[0], 0.0, 1.0, colors="g", linewidth=2.0, label="Flow 0")
ax2.vlines(ps.arrivals[1], 0.0, 0.7, colors="r", linewidth=2.0, label="Flow 1")
ax2.set_title("Departure times from DRR switch")
ax2.set_xlabel("time")
ax2.set_ylim([0, 1.5])
ax2.set_xlim([0, max(ps.arrivals[0]) + 10])
ax2.grid(True)
ax2.legend()

fig.savefig("drr.png")

plt.show()
