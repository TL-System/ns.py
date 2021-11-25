from random import random
import numpy as np


def paretovariate_generator(xmin=1e-3, alpha=2.0):
    """
    Pareto distribution.
    Parameters
    ----------------
    xmin:   positive real
            scale parameter, support [xmin, +inf)
    alpha:  positive real
            shape parameter

    Returns
    ----------------
    random variable conforming with Pareto(xmin, alpha)

    Note:
    mean = inf, if alpha <= 1
    mean = alpha * xmin / (alpha - 1), if alpha > 1
    """

    u = 1.0 - random()
    return xmin / u**(1.0 / alpha)


def pareto_onoff_generator(on_min=0.5 / 3,
                           on_alpha=1.5,
                           off_min=0.5 / 3,
                           off_alpha=1.5,
                           on_rate=2e5,
                           pktsize=1000):
    """
    Pareto on/off traffic generator
    Packets are sent at fixed rate during on periods, and no packets are sent during off periods.
    Both on and off periods are taken from a Pareto distribution with constant size packets.
    Parameters
    ----------------
    on_min:   positive real
            scale parameter, support [on_min, +inf)
    on_alpha:  positive real
            shape parameter
    off_min:   positive real
            scale parameter, support [off_min, +inf)
    off_alpha:  positive real
            shape parameter

    Yields
    ----------------
    current_iat: current interarrival time (sec)
    """
    interval = pktsize * 8 / on_rate
    remain_pkts = 0

    while True:
        if remain_pkts == 0:
            next_burstlen = np.ceil(
                paretovariate_generator(on_min, on_alpha) + 0.5)
            remain_pkts = next_burstlen
            next_idle_time = paretovariate_generator(off_min, off_alpha)
            current_iat = next_idle_time
        else:
            remain_pkts -= 1
            current_iat = interval
        yield current_iat
