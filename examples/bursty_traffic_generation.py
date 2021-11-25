import simpy
import numpy as np
import matplotlib.pyplot as plt

from functools import partial
from random import randint, seed

from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.utils.generators.pareto_onoff_generator import pareto_onoff_generator
from ns.utils.generators.MAP_MSP_generator import BMAP_generator

MIN_PKT_SIZE = 100
MAX_PKT_SIZE = 1500


def packet_size(myseed=None):
    seed(myseed)
    return randint(MIN_PKT_SIZE, MAX_PKT_SIZE)


def interarrival(y):
    try:
        return next(y)
    except StopIteration:
        return


if __name__ == '__main__':
    env = simpy.Environment()
    ps = PacketSink(env)
    simulation_time = 20
    pg_duration = 18

    # (1) to generate inter-arrival times ~ pareto-onoff model
    """
    y = pareto_onoff_generator(on_min=0.5 / 3,
                                on_alpha=1.5,
                                off_min=0.5 / 3,
                                off_alpha=1.5,
                                on_rate=2e5,
                                pktsize=(MIN_PKT_SIZE + MAX_PKT_SIZE) / 2)
    """

    # (2) to generate inter-arrival times ~ MAP or BMAP model
    D0 = np.array([[-114.46031, 11.3081, 8.42701],
                   [158.689, -29152.1587, 20.5697],
                   [1.08335, 0.188837, -1.94212]])
    D1 = np.array([[94.7252, 0.0, 0.0], [0.0, 2.89729e4, 0.0],
                   [0.0, 0.0, 0.669933]])
    y = BMAP_generator([D0, D1])

    iat_dist = partial(interarrival, y)
    # pkt_size_dist = partial(packet_size, myseed=10)
    pkt_size_dist = partial(packet_size)

    pg = DistPacketGenerator(env,
                             'flow_1',
                             iat_dist,
                             pkt_size_dist,
                             flow_id='flow_1',
                             initial_delay=0.0,
                             finish=pg_duration)

    pg.out = ps

    env.run(until=simulation_time)

    gen_time_stamps = ps.packet_times['flow_1']
    gen_pkt_sizes = ps.packet_sizes['flow_1']
    plt.figure(figsize=(10, 3))
    plt.plot(gen_time_stamps, gen_pkt_sizes, 'o', ms=3)
    plt.title('sample path of synthetic trace')
    plt.xlabel('time (sec)')
    plt.ylabel('pkt size (byte')
    plt.show()
