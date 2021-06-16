"""
In this example, we create a traffic shaper whose bucket size is the same as the 
packet size and whose bucket rate is one half the input packet rate.

The example also shows a method of plotting packet arrival and exit times.
"""
import simpy
import matplotlib.pyplot as plt

from ns.shaper.token_bucket import ShaperTokenBucket
from ns.packet.generator import PacketGenerator
from ns.packet.sink import PacketSink

if __name__ == '__main__':

    def const_arrival():
        return 2.5

    def const_size():
        return 100.0

    env = simpy.Environment()
    pg = PacketGenerator(env,
                         "pg",
                         const_arrival,
                         const_size,
                         initial_delay=7.0,
                         finish=35)
    pg2 = PacketGenerator(env,
                          "pg2",
                          const_arrival,
                          const_size,
                          initial_delay=7.0,
                          finish=35)
    ps = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)
    ps2 = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)
    source_rate = 8.0 * const_size() / const_arrival()
    bucket_rate = 0.5 * source_rate
    bucket_size = 1.0 * const_size()
    shaper = ShaperTokenBucket(env, bucket_rate, bucket_size)
    pg.out = ps
    pg2.out = shaper
    shaper.out = ps2
    env.run(until=10000)
    print(ps.arrivals)
    print(ps2.arrivals)

    fig, axis = plt.subplots()
    axis.vlines(ps.arrivals,
                0.0,
                1.0,
                colors="g",
                linewidth=2.0,
                label='input stream')
    axis.vlines(ps2.arrivals,
                0.0,
                0.7,
                colors="r",
                linewidth=2.0,
                label='output stream')
    axis.set_title("Arrival times")
    axis.set_xlabel("time")
    axis.set_ylim([0, 1.5])
    axis.set_xlim([0, max(ps2.arrivals) + 10])
    axis.legend()
    #axis.set_ylabel("normalized frequency of occurrence")
    #fig.savefig("ArrivalHistogram.png")
    plt.show()
