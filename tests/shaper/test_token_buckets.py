"""Rate/burst envelopes and identity when shapers share reordered buffers."""

import pytest
import simpy

from ns.packet.packet import Packet
from ns.port.port import Port
from ns.scheduler.sp import SPServer
from ns.shaper.token_bucket import TokenBucketShaper
from ns.shaper.two_rate_token_bucket import TwoRateTokenBucketShaper


class Sink:
    def __init__(self, env):
        self.env = env
        self.items = []

    def put(self, packet):
        self.items.append((self.env.now, packet, packet.color))


def make_shaper(env, two=False, **kwargs):
    if two:
        return TwoRateTokenBucketShaper(env, cir=800, cbs=100, **kwargs)
    return TokenBucketShaper(env, rate=800, bucket_size=100, **kwargs)


@pytest.mark.parametrize("two", [False, True])
def test_mixed_sizes_exact_fit_idle_cap_and_oversized_borrowing(two):
    env = simpy.Environment()
    shaper = make_shaper(env, two)
    shaper.out = sink = Sink(env)
    packets = [Packet(0, size, i) for i, size in enumerate([60, 40, 20, 200, 10])]
    for item in packets:
        shaper.put(item)
    env.run()
    assert [time for time, *_ in sink.items] == pytest.approx([0, 0, .2, 2.2, 2.3])
    assert [item for _, item, _ in sink.items] == packets
    env.run(until=100)
    shaper.put(Packet(env.now, 100, 5))
    shaper.put(Packet(env.now, 100, 6))
    env.run()
    assert [time for time, *_ in sink.items[-2:]] == [100, 101]
    assert shaper.packets_received == shaper.packets_sent == 7
    assert shaper.busy == 0


@pytest.mark.parametrize("two", [False, True])
def test_all_interdeparture_windows_obey_rate_burst_envelope(two):
    env = simpy.Environment()
    shaper = make_shaper(env, two)
    shaper.out = sink = Sink(env)
    for i, size in enumerate([10, 70, 20, 40, 1, 90, 100, 3]):
        shaper.put(Packet(0, size, i))
    env.run()
    for start in range(len(sink.items)):
        for stop in range(start, len(sink.items)):
            window = sink.items[start:stop + 1]
            assert sum(item.size for _, item, _ in window) <= (
                100 + 100 * (window[-1][0] - window[0][0]) + 1e-10
            )


def test_peak_serialization_and_tokens_accrue_during_service():
    env = simpy.Environment()
    shaper = make_shaper(env, peak=400)
    shaper.out = sink = Sink(env)
    for i in range(3):
        shaper.put(Packet(0, 100, i))
    env.run(until=1)
    assert shaper.busy == 1
    env.run()
    assert [time for time, *_ in sink.items] == [2, 4, 6]
    assert shaper.busy == 0


def test_two_rate_peak_wait_preserves_and_refills_committed_tokens():
    env = simpy.Environment()
    shaper = TwoRateTokenBucketShaper(env, 80, 10, 800, 100)
    shaper.out = sink = Sink(env)
    for i, size in enumerate([5, 95, 100, 10]):
        shaper.put(Packet(0, size, i))
    env.run()
    assert [time for time, *_ in sink.items] == pytest.approx([0, 0, 1, 1.1])
    assert [color for *_, color in sink.items] == ["green", "yellow", "red", "red"]
    # Yellow/red did not use committed tokens, and the wait replenished the cap.
    assert shaper.current_bucket_commit == 10
    assert shaper.current_bucket_peak == 0


@pytest.mark.parametrize("two", [False, True])
def test_zero_buffer_direct_input_needs_no_callback(two):
    env = simpy.Environment()
    shaper = make_shaper(env, two, zero_buffer=True)
    shaper.out = sink = Sink(env)
    item = Packet(0, 100, 0)
    shaper.put(item)
    env.run()
    assert sink.items[0][:2] == (0, item)
    assert not shaper.upstream_stores


@pytest.mark.parametrize("two", [False, True])
def test_retained_shaper_releases_selected_identity_after_priority_reordering(two):
    env = simpy.Environment()
    buffer = Port(env, 0, qlimit=3, zero_downstream_buffer=True)
    shaper = make_shaper(env, two, zero_buffer=True, zero_downstream_buffer=True)
    # Enough shaper credit to enqueue all three while the first is in service.
    if two:
        shaper.cbs = shaper.current_bucket_commit = 300
    else:
        shaper.bucket_size = shaper.current_bucket = 300
    scheduler = SPServer(env, 800, {0: 1, 1: 2}, zero_buffer=True)
    sink = Sink(env)
    buffer.out, shaper.out, scheduler.out = shaper, scheduler, sink
    packets = [Packet(0, 100, i, flow_id=int(i == 2)) for i in range(3)]
    releases = []
    original = buffer.update

    def release(item):
        original(item)
        releases.append((item, list(buffer.store.items), list(shaper.store.items)))

    buffer.update = release
    buffer.put(packets[0])
    env.run(until=.01)  # First is already in downstream nonpreemptive service.
    for item in packets[1:]:
        buffer.put(item)
    env.run(until=.1)
    assert buffer.byte_size == 300
    assert buffer.put(Packet(env.now, 1, 3)) is None
    env.run()
    first, low, high = packets
    assert [item for _, item, _ in sink.items] == [first, high, low]
    assert releases == [(first, [low, high], [low, high]),
                        (high, [low], [low]), (low, [], [])]
    assert buffer.byte_size == 0
    assert not shaper.upstream_stores
    assert not shaper.upstream_updates


@pytest.mark.parametrize("two", [False, True])
def test_targeted_release_is_idempotent_and_clears_hooks_before_callback(two):
    env = simpy.Environment()
    shaper = make_shaper(env, two, zero_buffer=True, zero_downstream_buffer=True)
    retained = simpy.Store(env)
    first, selected = Packet(0, 100, 7), Packet(0, 100, 7)
    retained.put(first)
    retained.put(selected)
    callbacks = []

    def release(item):
        assert item not in shaper.upstream_stores
        assert item not in shaper.upstream_updates
        callbacks.append(item)

    shaper.put(selected, upstream_update=release, upstream_store=retained)
    shaper.update(selected)
    shaper.update(selected)
    assert retained.items == [first]
    assert callbacks == [selected]


def test_two_rate_peak_and_green_envelopes_with_yellow_preserving_credit():
    env = simpy.Environment()
    shaper = TwoRateTokenBucketShaper(env, 80, 10, 800, 100)
    shaper.out = sink = Sink(env)

    def arrivals():
        previous = 0
        for i, (time, size) in enumerate([(0, 5), (0, 90), (.5, 5),
                                         (.5, 40), (1.5, 10)]):
            yield env.timeout(time - previous)
            previous = time
            shaper.put(Packet(time, size, i))

    env.process(arrivals())
    env.run()
    assert [time for time, *_ in sink.items] == [0, 0, .5, .5, 1.5]
    assert [color for *_, color in sink.items] == [
        "green", "yellow", "green", "yellow", "green"
    ]
    for start in range(len(sink.items)):
        for stop in range(start, len(sink.items)):
            window = sink.items[start:stop + 1]
            elapsed = window[-1][0] - window[0][0]
            assert sum(p.size for _, p, _ in window) <= 100 + 100 * elapsed
            assert sum(p.size for _, p, color in window if color == "green") <= (
                10 + 10 * elapsed
            )


def test_oversized_peak_packet_waits_and_empty_peak_defers_next_packet():
    env = simpy.Environment()
    shaper = TwoRateTokenBucketShaper(env, 80, 10, 800, 100)
    shaper.out = sink = Sink(env)
    shaper.put(Packet(0, 250, 0))
    shaper.put(Packet(0, 1, 1))
    env.run()
    assert [time for time, *_ in sink.items] == pytest.approx([1.5, 1.51])
    assert [color for *_, color in sink.items] == ["red", "red"]
    assert shaper.current_bucket_commit == 10


@pytest.mark.parametrize("kwargs", [
    {"rate": 0}, {"rate": -1}, {"rate": float("nan")},
    {"bucket_size": 0}, {"bucket_size": float("inf")}, {"peak": 0},
])
def test_invalid_single_rate_settings(kwargs):
    settings = dict(rate=800, bucket_size=100)
    settings.update(kwargs)
    with pytest.raises(ValueError):
        TokenBucketShaper(simpy.Environment(), **settings)


@pytest.mark.parametrize("kwargs", [
    {"cir": 0}, {"cbs": -1}, {"pir": 0, "pbs": 100},
    {"pir": 400, "pbs": 100}, {"pir": 800}, {"pbs": 100},
    {"pir": 800, "pbs": 0}, {"cir": float("inf")},
])
def test_invalid_two_rate_settings(kwargs):
    settings = dict(cir=800, cbs=100)
    settings.update(kwargs)
    with pytest.raises(ValueError):
        TwoRateTokenBucketShaper(simpy.Environment(), **settings)
