"""RFC 2698 metering uses bytes; ns.py rate arguments use bits/second."""

import pytest
import simpy

from ns.packet.packet import Packet
from ns.utils.misc import TrTCM


class Sink:
    def __init__(self, env):
        self.env = env
        self.items = []

    def put(self, packet):
        self.items.append((self.env.now, packet.color, packet))


def marker(env):
    element = TrTCM(env, pir=800, pbs=100, cir=400, cbs=50)
    element.out = Sink(env)
    return element


def test_colorblind_exact_fit_oversize_and_unused_committed_tokens():
    env = simpy.Environment()
    element = marker(env)
    packets = [Packet(0, size, i, flow_id="flow")
               for i, size in enumerate([25, 50, 25, 1, 101])]
    for item in packets:
        item.color = "red"  # Color-blind is the compatible default.
        element.put(item)
    assert [color for _, color, _ in element.out.items] == [
        "green", "yellow", "green", "red", "red"
    ]
    assert all(item.flow_id == "flow" for item in packets)
    assert all(time == 0 for time, _, _ in element.out.items)
    assert element.committed_bucket == element.peak_bucket == 0


def test_idle_refill_is_capped_and_uses_bits_to_bytes():
    env = simpy.Environment()
    element = marker(env)
    element.put(Packet(0, 100, 0))  # Yellow leaves C intact.
    env.run(until=.5)
    element.put(Packet(.5, 50, 1))
    env.run(until=100)
    element.put(Packet(100, 50, 2))
    element.put(Packet(100, 50, 3))
    element.put(Packet(100, 1, 4))
    assert [color for _, color, _ in element.out.items] == [
        "yellow", "green", "green", "yellow", "red"
    ]


def test_red_oversize_keeps_both_buckets_available_for_next_packet():
    env = simpy.Environment()
    element = marker(env)
    for i, size in enumerate([101, 50, 50]):
        element.put(Packet(0, size, i))
    assert [color for _, color, _ in element.out.items] == [
        "red", "green", "yellow"
    ]


@pytest.mark.parametrize("kwargs", [
    {"pir": 100}, {"pir": -1}, {"cir": -1}, {"pbs": 0},
    {"cbs": 0}, {"pir": float("inf")}, {"cir": float("nan")},
])
def test_invalid_marker_settings(kwargs):
    settings = dict(pir=800, pbs=100, cir=400, cbs=50)
    settings.update(kwargs)
    with pytest.raises(ValueError):
        TrTCM(simpy.Environment(), **settings)
