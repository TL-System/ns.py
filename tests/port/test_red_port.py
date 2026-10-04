"""RED uses explicit draws; queue capacity is independent of early drops."""

import pytest
import simpy

from ns.packet.packet import Packet
from ns.port.red_port import REDPort
from ns.scheduler.sp import SPServer


class Sink:
    def __init__(self, env):
        self.env = env
        self.items = []

    def put(self, packet):
        self.items.append((self.env.now, packet))


def port(env, **kwargs):
    settings = dict(max_threshold=100, min_threshold=50, max_probability=0.5)
    settings.update(kwargs)
    result = REDPort(env, settings.pop("rate", 800), **settings)
    result.out = Sink(env)
    return result


def test_unlimited_capacity_and_prearrival_ewma():
    env = simpy.Environment()
    red = port(env, weight_factor=1)
    packets = [Packet(0, 100, i) for i in range(3)]
    averages = []
    for item in packets:
        red.put(item)
        averages.append(red.average_queue_size)
    env.run()
    assert averages == [0, 0.5, 1.25]
    assert red.out.items == [(i + 1, item) for i, item in enumerate(packets)]
    assert (red.packets_received, red.packets_dropped, red.byte_size) == (3, 0, 0)


@pytest.mark.parametrize("limit_bytes,qlimit", [(False, 1), (True, 100)])
def test_capacity_counts_service_and_pending_get(limit_bytes, qlimit):
    env = simpy.Environment()
    red = port(env, qlimit=qlimit, limit_bytes=limit_bytes, element_id="red")
    env.run(until=0.1)
    first, second, third = [Packet(env.now, 100, i) for i in range(3)]
    assert red.put(first) is not None
    assert red.put(second) is None
    env.run(until=0.2)
    assert red.put(third) is None
    env.run()
    assert red.out.items == [(1.1, first)]
    assert red.packets_dropped == 2
    assert red._packets_removed == 1
    assert red.byte_size == 0
    assert first.perhop_time == second.perhop_time == {"red": 0.1}


def test_explicit_draws_and_forced_max_threshold(monkeypatch):
    env = simpy.Environment()
    red = port(env, min_threshold=1, max_threshold=3, weight_factor=0)
    draws = iter([0.24, 0.25])
    monkeypatch.setattr("ns.port.red_port.random.uniform", lambda *_: next(draws))
    packets = [Packet(0, 100, i) for i in range(7)]
    # Samples 0,1 admit without drawing; sample 2 has p=.25. Equality admits.
    for item in packets:
        red.put(item)
    env.run()
    assert [item for _, item in red.out.items] == [
        packets[0], packets[1], packets[3]
    ]
    assert red.packets_dropped == 4
    assert red._packets_removed == 3
    assert red.byte_size == 0


def test_minimum_and_zero_probability_do_not_drop_a_zero_draw(monkeypatch):
    env = simpy.Environment()
    red = port(env, min_threshold=0, max_threshold=3, max_probability=0,
               weight_factor=0)
    monkeypatch.setattr("ns.port.red_port.random.uniform", lambda *_: 0)
    for i in range(4):
        red.put(Packet(0, 100, i))
    env.run()
    assert [item.packet_id for _, item in red.out.items] == [0, 1, 2]
    assert red.packets_dropped == 1  # Max threshold still forces a drop.


def test_idle_average_decays_on_arrival_not_wall_clock():
    env = simpy.Environment()
    red = port(env, weight_factor=1, qlimit=10)
    red.put(Packet(0, 100, 0))
    red.put(Packet(0, 100, 1))
    env.run(until=100)
    assert red.average_queue_size == 0.5
    red.put(Packet(100, 100, 2))
    assert red.average_queue_size == 0.25
    env.run()


def test_byte_ewma_samples_existing_sizes_and_capacity_drop_updates_average():
    env = simpy.Environment()
    red = port(env, limit_bytes=True, qlimit=100, weight_factor=1)
    red.put(Packet(0, 100, 0))
    red.put(Packet(0, 1, 1))
    assert red.average_queue_size == 50
    assert red.packets_dropped == 1
    env.run()


def test_capacity_precedes_draw_and_default_weight_is_one_over_512(monkeypatch):
    env = simpy.Environment()
    red = port(env, qlimit=1, min_threshold=0, max_threshold=100)

    def unexpected_draw(*_):
        pytest.fail("A capacity drop must not consume a RED draw")

    monkeypatch.setattr("ns.port.red_port.random.uniform", unexpected_draw)
    red.put(Packet(0, 100, 0))
    red.put(Packet(0, 100, 1))
    assert red.average_queue_size == 1 / 512
    assert red.packets_dropped == 1
    env.run()


def test_retained_capacity_and_red_release_through_priority_scheduler():
    env = simpy.Environment()
    red = port(env, qlimit=3, zero_downstream_buffer=True)
    red.rate = 0
    scheduler = SPServer(env, 800, {0: 1, 1: 2}, zero_buffer=True)
    red.out = scheduler
    sink = Sink(env)
    scheduler.out = sink
    first, low, high = [Packet(0, 100, i, flow_id=int(i == 2)) for i in range(3)]
    red.put(first)
    env.run(until=.01)  # Establish nonpreemptive service before later arrivals.
    for item in [low, high]:
        red.put(item)
    env.run(until=0.1)
    assert red.byte_size == 300
    assert red.put(Packet(env.now, 100, 3)) is None
    env.run()
    assert [item for _, item in sink.items] == [first, high, low]
    assert red.byte_size == 0
    assert not red.store.items
    assert red._packets_removed == 3


@pytest.mark.parametrize("kwargs", [
    {"min_threshold": -1}, {"max_threshold": 50},
    {"max_probability": -0.1}, {"max_probability": 1.1},
    {"weight_factor": -1}, {"weight_factor": float("nan")},
    {"max_threshold": float("inf")}, {"qlimit": -1}, {"rate": -1},
])
def test_invalid_red_settings(kwargs):
    with pytest.raises(ValueError):
        port(simpy.Environment(), **kwargs)
