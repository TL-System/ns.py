import pytest
import simpy

from ns.packet.dist_generator import DistPacketGenerator


class Collector:
    def __init__(self):
        self.packets = []

    def put(self, packet):
        self.packets.append(packet)


def test_byte_limit_shortens_final_packet_and_finishes_without_extra_draw():
    env = simpy.Environment()
    intervals = iter([2])
    source = DistPacketGenerator(
        env, "source", lambda: next(intervals), lambda: 100,
        initial_delay=1, size=150, flow_id=7, rec_flow=True,
    )
    source.out = sink = Collector()
    env.run()
    assert [(p.time, p.size, p.packet_id, p.flow_id) for p in sink.packets] == [
        (1, 100, 0, 7), (3, 50, 1, 7)
    ]
    assert (source.packets_sent, source.sent_size, env.now) == (2, 150, 3)
    assert source.time_rec == [1, 3]
    assert source.size_rec == [100, 50]


def test_finish_is_exclusive_and_does_not_wait_past_stop():
    env = simpy.Environment()
    source = DistPacketGenerator(env, "source", lambda: 2, lambda: 10, finish=3)
    source.out = sink = Collector()
    env.run()
    assert [p.time for p in sink.packets] == [0, 2]
    assert env.now == 3


@pytest.mark.parametrize("limit", [{"size": 0}, {"initial_delay": 2, "finish": 2}])
def test_empty_source_never_draws_packet_size(limit):
    env = simpy.Environment()
    source = DistPacketGenerator(env, "source", lambda: 1, lambda: 1 / 0, **limit)
    source.out = Collector()
    env.run()
    assert source.packets_sent == 0


def test_zero_intervals_form_a_finite_simultaneous_burst():
    env = simpy.Environment()
    source = DistPacketGenerator(env, "source", lambda: 0, lambda: 10, size=30)
    source.out = sink = Collector()
    env.run()
    assert [p.time for p in sink.packets] == [0, 0, 0]
    assert source.sent_size == 30


def test_downstream_mutation_cannot_change_source_budget_or_records():
    env = simpy.Environment()
    source = DistPacketGenerator(
        env, "source", lambda: 1, lambda: 30, size=60, finish=3, rec_flow=True,
    )
    observed_counts = []

    class MutatingSink:
        def put(self, packet):
            observed_counts.append(source.packets_sent)
            packet.size = 1
            packet.time = 99

    source.out = MutatingSink()
    env.run()
    assert observed_counts == [1, 2]
    assert (source.packets_sent, source.sent_size) == (2, 60)
    assert source.time_rec == [0, 1]
    assert source.size_rec == [30, 30]


@pytest.mark.parametrize("interval", [-1, float("nan"), float("inf")])
def test_invalid_interarrival_fails_before_scheduling(interval):
    env = simpy.Environment()
    source = DistPacketGenerator(env, "source", lambda: interval, lambda: 10)
    source.out = Collector()
    with pytest.raises(ValueError, match="interval"):
        env.run()


@pytest.mark.parametrize("size", [-1, float("nan"), float("inf")])
def test_invalid_packet_size_never_reaches_downstream(size):
    env = simpy.Environment()
    source = DistPacketGenerator(env, "source", lambda: 1, lambda: size, finish=2)
    source.out = sink = Collector()
    with pytest.raises(ValueError, match="size"):
        env.run()
    assert sink.packets == []


def test_zero_byte_draw_is_a_packet_and_does_not_spend_the_byte_budget():
    env = simpy.Environment()
    sizes = iter([0, 10])
    source = DistPacketGenerator(
        env, "source", lambda: 1, lambda: next(sizes), size=10,
    )
    source.out = sink = Collector()
    env.run()
    assert [(p.time, p.size) for p in sink.packets] == [(0, 0), (1, 10)]
    assert (source.packets_sent, source.sent_size) == (2, 10)
