"""Hand-calculated DRR visits; packet sizes and quanta are bytes."""

import math

import pytest
import simpy

from ns.packet.packet import Packet
from ns.scheduler.drr import DRRServer


class CaptureSink:
    def __init__(self, env):
        self.env = env
        self.received = []

    def put(self, packet):
        self.received.append((self.env.now, packet))


class RetainingSink:
    def __init__(self, env):
        self.env = env
        self.received = []

    def put(self, packet, upstream_update, upstream_store):
        self.received.append(
            (self.env.now, packet, upstream_update, upstream_store)
        )

    def release(self, index):
        _, packet, update, store = self.received[index]
        assert store.get().value is packet
        update(packet)


def make_server(env, weights=(1, 1), rate=12000, **kwargs):
    server = DRRServer(env, rate=rate, weights=list(weights), **kwargs)
    server.out = CaptureSink(env)
    return server


def packet(packet_id, flow_id, size=1500):
    return Packet(0, size, packet_id, flow_id=flow_id)


def enqueue_at(env, server, when, *packets):
    def send():
        yield env.timeout(when)
        for item in packets:
            server.put(item)

    env.process(send())


def assert_departures(server, expected, times):
    assert [item for _, item in server.out.received] == expected
    assert [time for time, _ in server.out.received] == pytest.approx(times)
    assert server.current_packet is None
    assert server.total_packets() == 0
    assert all(server.byte_size(queue_id) == 0 for queue_id in server.all_flows())


def test_jumbo_accumulates_fixed_credit_while_other_class_progresses():
    env = simpy.Environment()
    server = make_server(env)
    jumbo = packet(0, 0, 4500)
    small = [packet(i, 1) for i in range(1, 4)]
    for item in [jumbo, *small]:
        server.put(item)
    env.run()

    # 1500-byte rounds: class 0 needs three visits; class 1 sends in each.
    assert_departures(server, [small[0], small[1], jumbo, small[2]], [1, 2, 5, 6])
    assert server.base_quantum == 1500
    assert server.quantum == {0: 1500, 1: 1500}


def test_deficit_carries_only_while_class_remains_backlogged():
    env = simpy.Environment()
    server = make_server(env)
    a = [packet(i, 0, 1000) for i in range(3)]
    b = [packet(i + 3, 1, 1000) for i in range(3)]
    for item in [*a, *b]:
        server.put(item)
    env.run()

    # Each first visit leaves 500 bytes. The second has 2000, enough for two.
    assert_departures(server, [a[0], b[0], a[1], a[2], b[1], b[2]],
                      [2 / 3, 4 / 3, 2, 8 / 3, 10 / 3, 4])
    assert server.deficit == {0: 0, 1: 0}


def test_empty_at_selection_resets_credit_before_arrival_during_service():
    env = simpy.Environment()
    server = make_server(env)
    first = packet(0, 0, 1000)
    b = [packet(i, 1) for i in (1, 2)]
    later = [packet(i, 0, 900) for i in (3, 4)]
    for item in [first, *b]:
        server.put(item)
    enqueue_at(env, server, 0.2, *later)
    env.run()

    # Selecting first empties A: its unused 500 bytes cannot reach later arrivals.
    # A's fresh 1500-byte visit sends only one 900-byte packet before B's turn.
    assert_departures(server, [first, b[0], later[0], b[1], later[1]],
                      [2 / 3, 5 / 3, 34 / 15, 49 / 15, 58 / 15])


def test_arrival_to_current_backlogged_class_does_not_move_its_next_turn():
    env = simpy.Environment()
    server = make_server(env, weights=(1, 1, 1))
    a0 = packet(0, 0, 1000)
    a1 = packet(1, 0)
    a2 = packet(2, 0)
    b = packet(3, 1)
    c = packet(4, 2)
    server.put(a0)
    server.put(a1)
    enqueue_at(env, server, 0.1, b)
    enqueue_at(env, server, 0.2, a2)
    enqueue_at(env, server, 0.3, c)
    env.run()

    # B and C join during A's visit. A joins their tail when its 500-byte
    # residual fails to cover a1, rather than when a2 arrives mid-service.
    assert_departures(server, [a0, b, c, a1, a2],
                      [2 / 3, 5 / 3, 8 / 3, 11 / 3, 14 / 3])


def test_active_order_is_activation_fifo_even_for_reverse_class_ids():
    env = simpy.Environment()
    server = make_server(env, weights=(1, 1, 1))
    packets = [packet(i, queue_id) for i, queue_id in enumerate([2, 0, 1])]
    for item in packets:
        server.put(item)
    env.run()

    # This active-list variant follows first activation, unlike Days' class cursor.
    assert_departures(server, packets, [1, 2, 3])


def test_weights_are_byte_quanta_and_fifo_holds_within_a_mapped_class(capsys):
    env = simpy.Environment()
    server = DRRServer(
        env, 12000, {"a": 1, "b": 2},
        flow_classes=lambda p: "a" if p.flow_id in (10, 11) else "b",
        debug=True,
    )
    server.out = CaptureSink(env)
    a = [packet(0, 10), packet(1, 11)]
    b = [packet(i, 20) for i in range(2, 6)]
    for item in [a[0], b[0], a[1], *b[1:]]:
        server.put(item)
    env.run()

    assert_departures(server, [a[0], b[0], b[1], a[1], b[2], b[3]],
                      [1, 2, 3, 4, 5, 6])
    assert "class a" in capsys.readouterr().out


def test_sole_jumbo_adds_rounds_without_idling_the_link():
    env = simpy.Environment()
    server = make_server(env, weights=(1,))
    jumbo = packet(0, 0, 9000)
    enqueue_at(env, server, 2, jumbo)
    env.run()

    # Six logical credit rounds consume no simulation time; service lasts 6 s.
    assert_departures(server, [jumbo], [8])
    assert server.quantum == {0: 1500}


def test_new_eligible_class_does_not_preempt_a_serializing_jumbo():
    env = simpy.Environment()
    server = make_server(env)
    first = packet(0, 0, 3000)
    later = packet(1, 1)
    server.put(first)
    enqueue_at(env, server, 0.5, later)
    env.run()

    assert_departures(server, [first, later], [2, 3])


def test_same_time_arrival_can_progress_while_jumbo_accumulates_credit():
    env = simpy.Environment()
    server = make_server(env)
    jumbo = packet(0, 0, 4500)
    small = packet(1, 1)
    server.put(jumbo)
    enqueue_at(env, server, 0, small)
    env.run()

    # The zero-time arrival is already scheduled before service selection.
    # Logical credit rounds must not run past it and choose the jumbo early.
    assert_departures(server, [small, jumbo], [1, 4])


def test_waiting_telemetry_excludes_service_and_uses_class_ids():
    env = simpy.Environment()
    server = DRRServer(env, 12000, {"a": 1}, flow_classes=lambda p: "a")
    server.out = CaptureSink(env)
    first = packet(0, 10, 1000)
    second = packet(1, 11, 500)
    server.put(first)
    server.put(second)
    env.run(until=0.25)

    assert server.packet_in_service() is first
    assert server.size("a") == server.total_packets() == 1
    assert server.byte_size("a") == 500
    assert list(server.all_flows()) == ["a"]
    env.run()
    assert_departures(server, [first, second], [2 / 3, 1])


def test_explicit_mtu_sets_quantum_once_instead_of_observing_packet_sizes():
    env = simpy.Environment()
    server = make_server(env, weights=(1, 2), mtu_bytes=3000)
    jumbo = packet(0, 0, 9000)
    small = [packet(i, 1) for i in range(1, 5)]
    for item in [jumbo, *small]:
        server.put(item)
    env.run()

    assert_departures(server, [*small, jumbo], [1, 2, 3, 4, 10])
    assert server.quantum == {0: 3000, 1: 6000}


def test_zero_buffer_handoff_preserves_identity_and_releases_upstream_once():
    env = simpy.Environment()
    server = make_server(env, weights=(1,), zero_buffer=True,
                         zero_downstream_buffer=True)
    server.out = RetainingSink(env)
    upstream = simpy.Store(env)
    released = []
    packets = [packet(0, 0, 1000), packet(1, 0, 2000)]
    for item in packets:
        upstream.put(item)
        server.put(item, upstream_update=released.append, upstream_store=upstream)
    env.run()

    assert [entry[1] for entry in server.out.received] == packets
    assert [entry[0] for entry in server.out.received] == pytest.approx([2 / 3, 2])
    assert server.stores[0].items == upstream.items == packets
    assert released == []
    server.out.release(0)
    assert server.stores[0].items == upstream.items == [packets[1]]
    server.out.release(1)
    assert released == packets
    assert not server.stores[0].items
    assert not upstream.items
    assert not server.upstream_stores
    assert not server.upstream_updates
    assert server.size(0) == server.byte_size(0) == 0


@pytest.mark.parametrize("weights", [[], [0], [-1], [math.nan], [math.inf]])
def test_weights_must_define_finite_positive_byte_credit(weights):
    with pytest.raises(ValueError, match="weight"):
        DRRServer(simpy.Environment(), 12000, weights)


@pytest.mark.parametrize("rate", [0, -1, math.nan, math.inf])
def test_rate_rejects_invalid_serialization_intervals(rate):
    with pytest.raises(ValueError, match="rate"):
        DRRServer(simpy.Environment(), rate, [1])


@pytest.mark.parametrize("mtu", [0, -1, math.nan, math.inf])
def test_mtu_rejects_invalid_byte_credit(mtu):
    with pytest.raises(ValueError, match="mtu"):
        DRRServer(simpy.Environment(), 12000, [1], mtu_bytes=mtu)


def test_unknown_class_is_rejected_before_changing_queue_accounting():
    env = simpy.Environment()
    server = make_server(env, weights=(1,))
    with pytest.raises(ValueError, match="class"):
        server.put(packet(0, 1))
    env.run()
    assert server.packets_received == server.total_packets() == 0
    assert server.out.received == []


def test_zero_buffer_accepts_direct_packets_without_upstream_hooks():
    env = simpy.Environment()
    server = make_server(env, weights=(1,), zero_buffer=True)
    item = packet(0, 0)
    server.put(item)
    env.run()
    assert_departures(server, [item], [1])


def test_none_is_a_valid_mapped_class_id():
    env = simpy.Environment()
    server = DRRServer(env, 12000, {None: 1}, flow_classes=lambda p: None)
    server.out = CaptureSink(env)
    item = packet(0, 10)
    server.put(item)
    env.run()

    assert_departures(server, [item], [1])


def test_none_class_keeps_normal_deficit_visits_while_backlogged():
    env = simpy.Environment()
    server = DRRServer(env, 12000, {None: 1, "other": 1})
    server.out = CaptureSink(env)
    a = [packet(i, None, 1000) for i in range(3)]
    b = [packet(i + 3, "other") for i in range(2)]
    for item in [*a, *b]:
        server.put(item)
    env.run()

    # None is a class key, so its 500-byte residual carries to a 2000-byte visit.
    assert_departures(server, [a[0], b[0], a[1], a[2], b[1]],
                      [2 / 3, 5 / 3, 7 / 3, 3, 4])
