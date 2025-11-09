"""
Illustrates DRR behavior when one flow injects jumbo frames while another
continues to send MTU-sized packets. The server inflates its quantum so jumbo
packets still depart, but printing the per-packet timestamps shows both flows
sharing the link.
"""

import simpy
import matplotlib.pyplot as plt

from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.scheduler.drr import DRRServer
from ns.utils.splitter import Splitter


def jumbo_arrival():
    return 0.002


def mtu_arrival():
    return 0.0015


def jumbo_size():
    return 9000.0


def mtu_size():
    return 1500.0


env = simpy.Environment()

jumbo_pg = DistPacketGenerator(
    env,
    "jumbo_flow",
    jumbo_arrival,
    jumbo_size,
    initial_delay=0.0,
    finish=0.05,
    flow_id=0,
)

mtu_pg = DistPacketGenerator(
    env,
    "mtu_flow",
    mtu_arrival,
    mtu_size,
    initial_delay=0.0,
    finish=0.05,
    flow_id=1,
)

input_tap_0 = PacketSink(env)
input_tap_1 = PacketSink(env)
sink = PacketSink(env)

server_rate = 10e9
server = DRRServer(env, server_rate, [1, 1], debug=False)

splitter_0 = Splitter()
splitter_1 = Splitter()

jumbo_pg.out = splitter_0
mtu_pg.out = splitter_1

splitter_0.out1 = server
splitter_0.out2 = input_tap_0
splitter_1.out1 = server
splitter_1.out2 = input_tap_1

server.out = sink

env.run(until=0.1)

print("Arrivals at DRR input, flow 0 (jumbo):")
print(input_tap_0.arrivals[0])

print("Arrivals at DRR input, flow 1 (mtu):")
print(input_tap_1.arrivals[1])

print("Departures at sink, flow 0 (jumbo):")
print(sink.arrivals[0])

print("Departures at sink, flow 1 (mtu):")
print(sink.arrivals[1])

print("Final DRR base quantum (bytes):", server.base_quantum)
print("Per-flow quanta:", server.quantum)

fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, sharex=True)
ax1.vlines(input_tap_0.arrivals[0], 0.0, 1.0, colors="g", linewidth=2.0, label="Flow 0")
ax1.vlines(input_tap_1.arrivals[1], 0.0, 0.7, colors="r", linewidth=2.0, label="Flow 1")
ax1.set_title("Arrival times at DRR switch (before service)")
ax1.set_ylim([0, 1.5])
ax1.set_xlim([0, max(sink.arrivals[0] + sink.arrivals[1]) + 0.01])
ax1.grid(True)
ax1.legend()

ax2.vlines(sink.arrivals[0], 0.0, 1.0, colors="g", linewidth=2.0, label="Flow 0")
ax2.vlines(sink.arrivals[1], 0.0, 0.7, colors="r", linewidth=2.0, label="Flow 1")
ax2.set_title("Departure times from DRR switch")
ax2.set_xlabel("time")
ax2.set_ylim([0, 1.5])
ax2.set_xlim([0, max(sink.arrivals[0] + sink.arrivals[1]) + 0.01])
ax2.grid(True)
ax2.legend()

fig.savefig("drr_jumbo.png")
plt.show()
