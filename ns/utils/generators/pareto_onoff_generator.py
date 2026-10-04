import math
from collections.abc import Iterator
from random import random


def paretovariate_generator(xmin: float = 1e-3, alpha: float = 2.0) -> float:
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

    if not math.isfinite(xmin) or xmin <= 0:
        raise ValueError("Pareto xmin must be finite and positive.")
    if not math.isfinite(alpha) or alpha <= 0:
        raise ValueError("Pareto alpha must be finite and positive.")
    # Invert F(x) = 1 - (xmin / x)**alpha with a uniform draw in [0, 1).
    u = 1.0 - random()
    return xmin / u ** (1.0 / alpha)


def pareto_onoff_generator(
    on_min: float = 0.5 / 3,
    on_alpha: float = 1.5,
    off_min: float = 0.5 / 3,
    off_alpha: float = 1.5,
    on_rate: float = 2e5,
    pktsize: float = 1000,
) -> Iterator[float]:
    """
    Pareto on/off traffic generator.

    On/off durations are seconds, independently drawn from Pareto distributions.
    Each burst emits its first packet at the start of the on period, then packets
    spaced by ``8 * pktsize / on_rate`` strictly before the on period ends. This
    packetizes a constant-rate source; even a short on period emits one packet.
    The source starts off. Combine this interarrival iterator with a packet
    source that consumes intervals; DistPacketGenerator itself emits at start
    before consuming its first interval.
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
    on_rate: positive real
            on-period rate in bits/second
    pktsize: positive real
            constant packet size in bytes

    Yields
    ----------------
    current_iat: current interarrival time (sec)
    """
    parameters = (on_min, on_alpha, off_min, off_alpha, on_rate, pktsize)
    if any(not math.isfinite(value) or value <= 0 for value in parameters):
        raise ValueError("on/off parameters must be finite and positive.")
    # Convert packet bytes to bits before dividing by the bit/second rate.
    packet_bits = pktsize * 8
    interval = packet_bits / on_rate
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("packet interval must be finite and positive.")

    tail = 0
    while True:
        on_duration = paretovariate_generator(on_min, on_alpha)
        off_duration = paretovariate_generator(off_min, off_alpha)
        # The gap includes the previous on period's unsent tail (initially zero).
        yield off_duration + tail
        # Compare packet bits against the on-period bit budget. Dividing by the
        # rate first can round an endpoint below finish and admit an extra packet.
        packet_index = 1
        while packet_index * packet_bits < on_duration * on_rate:
            yield interval
            packet_index += 1
        tail = on_duration - (packet_index - 1) * packet_bits / on_rate
