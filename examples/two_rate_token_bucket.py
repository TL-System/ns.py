"""
In this example, we create a traffic shaper whose bucket size is the same as the
packet size and whose bucket rate is one half the input packet rate.

The example also shows a method of plotting packet arrival and exit times.
"""
import simpy
import matplotlib.pyplot as plt

from ns.shaper.two_rate_token_bucket import TwoRateTokenBucketShaper
from ns.packet.dist_generator import PacketDistGenerator
from ns.packet.sink import PacketSink


def packet_arrival():
    return 2.5


def packet_size():
    return 1500.0


env = simpy.Environment()
pg1 = PacketDistGenerator(env,
                          "flow_0",
                          packet_arrival,
                          packet_size,
                          initial_delay=7.0,
                          finish=35)
pg2 = PacketDistGenerator(env,
                          "flow_1",
                          packet_arrival,
                          packet_size,
                          initial_delay=7.0,
                          finish=35)
ps = PacketSink(env, rec_flow_ids=False)

source_rate = 8.0 * packet_size() / packet_arrival()
cir = 0.5 * source_rate
cbs = 1.0 * packet_size()
pir = 0.8 * source_rate
pbs = 1.0 * packet_size()

shaper = TwoRateTokenBucketShaper(env, cir, cbs, pir, pbs, debug=True)

pg1.out = ps
pg2.out = shaper
shaper.out = ps

env.run(until=10000)

print(ps.arrivals)
print(ps.arrivals['flow_0'])
print(ps.arrivals['flow_1'])

fig, axis = plt.subplots()
axis.vlines(ps.arrivals['flow_0'],
            0.0,
            1.0,
            colors="g",
            linewidth=2.0,
            label='input stream')
axis.vlines(ps.arrivals['flow_1'],
            0.0,
            0.7,
            colors="r",
            linewidth=2.0,
            label='output stream')
axis.set_title("Arrival times")
axis.set_xlabel("time")
axis.set_ylim([0, 1.5])
axis.set_xlim([0, max(ps.arrivals['flow_1']) + 10])
axis.legend()
plt.show()
