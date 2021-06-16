"""
An example of creating a traffic shaper whose bucket size is the same as the
packet size and whose bucket rate is half of the input packet rate.
"""
import simpy
import matplotlib.pyplot as plt

from ns.packet.dist_generator import PacketDistGenerator
from ns.packet.sink import PacketSink
from ns.shaper.token_bucket import TokenBucketShaper


def packet_arrival():
    return 2.5


def packet_size():
    return 100.0


env = simpy.Environment()
pg1 = PacketDistGenerator(env,
                          "flow_0",
                          packet_arrival,
                          packet_size,
                          initial_delay=7.0,
                          finish=35,
                          flow_id=0)
pg2 = PacketDistGenerator(env,
                          "flow_1",
                          packet_arrival,
                          packet_size,
                          initial_delay=7.0,
                          finish=35,
                          flow_id=1)
ps1 = PacketSink(env)
ps2 = PacketSink(env)

source_rate = 8.0 * packet_size() / packet_arrival()

shaper = TokenBucketShaper(env, 0.5 * source_rate, 1.0 * packet_size())

pg1.out = ps1
pg2.out = shaper
shaper.out = ps2
env.run(until=100)

print(ps1.arrivals)
print(ps2.arrivals)

fig, axis = plt.subplots()

axis.vlines(ps1.arrivals[0],
            0.0,
            1.0,
            colors="g",
            linewidth=2.0,
            label='input stream of packets')
axis.vlines(ps2.arrivals[1],
            0.0,
            0.7,
            colors="r",
            linewidth=2.0,
            label='output stream of packets')

axis.set_title("Arrival times")
axis.set_xlabel("time")
axis.set_ylim([0, 1.5])
axis.set_xlim([0, max(ps2.arrivals[1]) + 10])
axis.legend()
fig.savefig("token_bucket.png")
plt.show()
