"""
An example of using the Weighted Fair Queueing (WFQ) scheduler.
"""
import simpy
import matplotlib.pyplot as plt

from ns.packet.dist_generator import PacketDistGenerator
from ns.packet.sink import PacketSink
from ns.utils.components import SnoopSplitter
from ns.scheduler.wfq import WFQServer


def packet_arrival():
    return 1.75


def const_size():
    return 1000.0


env = simpy.Environment()
pg1 = PacketDistGenerator(env,
                          "flow_0",
                          packet_arrival,
                          const_size,
                          initial_delay=0.0,
                          finish=35,
                          flow_id=0)
pg2 = PacketDistGenerator(env,
                          "flow_1",
                          packet_arrival,
                          const_size,
                          initial_delay=10.0,
                          finish=35,
                          flow_id=1)
ps = PacketSink(env)
ps_snoop1 = PacketSink(env)
ps_snoop2 = PacketSink(env)

source_rate = 8.0 * const_size() / packet_arrival()
wfq_server = WFQServer(env, source_rate, [1, 2], debug=True)
snoop1 = SnoopSplitter()
snoop2 = SnoopSplitter()

pg1.out = snoop1
pg2.out = snoop2

snoop1.out1 = wfq_server
snoop1.out2 = ps_snoop1
snoop2.out1 = wfq_server
snoop2.out2 = ps_snoop2

wfq_server.out = ps

env.run(until=100)

print("At the packet sink, packet arrival times for flow 0 are:")
print(ps.arrivals[0])

print("At the packet sink, packet arrival times for flow 1 are:")
print(ps.arrivals[1])

fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, sharex=True)
ax1.vlines(ps_snoop1.arrivals[0],
           0.0,
           1.0,
           colors="g",
           linewidth=2.0,
           label='Flow 0')
ax1.vlines(ps_snoop2.arrivals[1],
           0.0,
           0.7,
           colors="r",
           linewidth=2.0,
           label='Flow 1')
ax1.set_title("Arrival times at WFQ switch")
ax1.set_ylim([0, 1.5])
ax1.set_xlim([0, max(ps.arrivals[0]) + 10])
ax1.grid(True)
ax1.legend()

ax2.vlines(ps.arrivals[0], 0.0, 1.0, colors="g", linewidth=2.0, label='Flow 0')
ax2.vlines(ps.arrivals[1], 0.0, 0.7, colors="r", linewidth=2.0, label='Flow 1')
ax2.set_title("Departure times from WFQ switch")
ax2.set_xlabel("time")
ax2.set_ylim([0, 1.5])
ax2.set_xlim([0, max(ps.arrivals[0]) + 10])
ax2.grid(True)
ax2.legend()

fig.savefig("wfq.png")

plt.show()
