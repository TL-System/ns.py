import pytest
import simpy

from ns.packet.packet import Packet
from ns.utils.delayer import Delayer, StackDelayer


class CaptureSink:
    def __init__(self, env):
        self.env = env
        self.observed = []

    def put(self, packet):
        self.observed.append((self.env.now, packet))


def test_delayer_respects_draws_and_fifo_when_later_deadlines_are_earlier(monkeypatch):
    env = simpy.Environment()
    draws = iter([1, 0, 0])
    monkeypatch.setattr("ns.utils.delayer.uniform", lambda low, high: next(draws))
    delayer = Delayer(env, 1)
    sink = CaptureSink(env)
    delayer.out = sink
    packets = [Packet(time, 100, index) for index, time in enumerate([0, 0.2, 0.8])]

    def supply():
        for packet in packets:
            yield env.timeout(packet.time - env.now)
            delayer.put(packet)

    env.process(supply())
    env.run()

    assert [time for time, _ in sink.observed] == [1, 1, 1]
    assert [packet for _, packet in sink.observed] == packets
    assert all(observed is sent for (_, observed), sent in zip(sink.observed, packets))


def test_delayer_can_wait_idle_between_bursts_and_zero_delay_preserves_identity():
    env = simpy.Environment()
    delayer = Delayer(env, 0)
    sink = CaptureSink(env)
    delayer.out = sink
    first, second = Packet(0, 100, 0), Packet(2, 100, 1)

    def supply():
        delayer.put(first)
        yield env.timeout(2)
        delayer.put(second)

    env.process(supply())
    env.run()

    assert sink.observed == [(0, first), (2, second)]
    assert all(
        observed is sent
        for (_, observed), sent in zip(sink.observed, [first, second])
    )


def test_stack_delayer_serializes_bytes_at_bytes_per_second_and_waits_when_idle():
    env = simpy.Environment()
    delayer = StackDelayer(env, speed=100)
    sink = CaptureSink(env)
    delayer.out = sink
    first, second, third = Packet(0, 100, 0), Packet(0, 50, 1), Packet(2, 25, 2)

    def supply():
        delayer.put(first)
        delayer.put(second)
        yield env.timeout(2)
        delayer.put(third)

    env.process(supply())
    env.run()

    assert sink.observed == [(1, first), (1.5, second), (2.25, third)]
    assert all(
        observed is sent
        for (_, observed), sent in zip(sink.observed, [first, second, third])
    )


def test_stack_delayer_unlimited_speed_still_yields_and_forwards_in_order():
    env = simpy.Environment()
    delayer = StackDelayer(env, speed=float("inf"))
    sink = CaptureSink(env)
    delayer.out = sink
    packets = [Packet(0, size, index) for index, size in enumerate([100, 0, 50])]
    for packet in packets:
        delayer.put(packet)
    assert sink.observed == []

    env.run()

    assert sink.observed == [(0, packet) for packet in packets]
    assert all(observed is sent for (_, observed), sent in zip(sink.observed, packets))


@pytest.mark.parametrize("max_delay", [-1, float("nan"), float("inf")])
def test_delayer_rejects_invalid_delay(max_delay):
    with pytest.raises(ValueError):
        Delayer(simpy.Environment(), max_delay)


@pytest.mark.parametrize("speed", [0, -1, float("nan")])
def test_stack_delayer_rejects_nonpositive_speed(speed):
    with pytest.raises(ValueError):
        StackDelayer(simpy.Environment(), speed)
