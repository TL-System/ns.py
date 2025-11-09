"""
An example of using a token bucket shaper whose bucket size is the same as the
packet size, and whose bucket rate is half of the input packet rate.

This example also shows a method of plotting packet arrival and exit times.
"""

import simpy
import matplotlib.pyplot as plt

from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.shaper.token_bucket import TokenBucketShaper


def packet_arrival():
    return 2.5


def packet_size():
    return 100.0


env = simpy.Environment()
pg1 = DistPacketGenerator(
    env, "flow_1", packet_arrival, packet_size, initial_delay=7.0, finish=35
)

pg2 = DistPacketGenerator(
    env, "flow_2", packet_arrival, packet_size, initial_delay=7.0, finish=35
)

ps = PacketSink(env, rec_flow_ids=False)

source_rate = 8.0 * packet_size() / packet_arrival()

shaper = TokenBucketShaper(
    env, rate=0.5 * source_rate, peak=0.7 * source_rate, bucket_size=1.0 * packet_size()
)

pg1.out = ps
pg2.out = shaper
shaper.out = ps
env.run(until=100)

print(f"Packet arrival times in flow 1: {ps.arrivals['flow_1']}")
print(f"Packet arrival times in flow 2: {ps.arrivals['flow_2']}")

fig, axis = plt.subplots()

axis.vlines(
    ps.arrivals["flow_1"],
    0.0,
    1.0,
    colors="g",
    linewidth=2.0,
    label="input stream of packets",
)
axis.vlines(
    ps.arrivals["flow_2"],
    0.0,
    0.7,
    colors="r",
    linewidth=2.0,
    label="output stream of packets",
)

axis.set_title("Arrival times")
axis.set_xlabel("time")
axis.set_ylim([0, 1.5])
axis.set_xlim([0, max(ps.arrivals["flow_1"]) + 10])
axis.legend()
fig.savefig("token_bucket.png")
plt.show()
