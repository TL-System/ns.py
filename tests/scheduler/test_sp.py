"""Observable strict-priority service, queue accounting, and buffer ownership."""

import pytest
import simpy

from ns.packet.packet import Packet
from ns.scheduler.monitor import ServerMonitor
from ns.scheduler.sp import SPServer


class CaptureSink:
    def __init__(self, env):
        self.env = env
        self.received = []
        self.handoffs = []

    def put(self, packet, upstream_update=None, upstream_store=None):
        self.received.append((self.env.now, packet))
        self.handoffs.append((packet, upstream_update, upstream_store))


def packet(packet_id, flow_id=0, size=100):
    return Packet(0, size, packet_id, flow_id=flow_id)


def server_with_sink(env, priorities, **kwargs):
    server = SPServer(env, rate=800, priorities=priorities, **kwargs)
    server.out = CaptureSink(env)
    return server


@pytest.mark.parametrize("priorities", [[-2, 4, 4], {0: -2, 1: 4, 2: 4}])
def test_larger_priority_wins_and_equal_priorities_keep_arrival_order(priorities):
    env = simpy.Environment()
    server = server_with_sink(env, priorities)
    packets = [packet(0, 0, 40), packet(1, 2, 20), packet(2, 1, 30)]
    for item in packets:
        server.put(item)
    env.run()

    # Equal-priority flows share a FIFO; priority numbers need not be class IDs.
    assert [item for _, item in server.out.received] == [
        packets[1], packets[2], packets[0]
    ]
    assert [time for time, _ in server.out.received] == pytest.approx([0.2, 0.5, 0.9])


def test_priority_is_reconsidered_after_each_nonpreemptive_packet():
    env = simpy.Environment()
    server = server_with_sink(env, {0: 1, 1: 9})
    first = packet(0, 0)
    waiting_low = packet(1, 0, 40)
    later_high = packet(2, 1, 10)
    server.put(first)
    server.put(waiting_low)

    def arrival():
        yield env.timeout(0.25)
        server.put(later_high)

    env.process(arrival())
    env.run()

    assert server.out.received == [
        (1, first), (1.1, later_high), (1.5, waiting_low)
    ]
    assert first.prio[server.element_id] == 1
    assert later_high.prio[server.element_id] == 9


def test_arrival_at_completion_is_eligible_for_the_next_selection():
    env = simpy.Environment()
    server = server_with_sink(env, [1, 9])
    first, low, high = packet(0), packet(1), packet(2, 1)
    server.put(first)
    server.put(low)

    def arrival():
        # Insert the arrival timeout after the in-service completion timeout.
        yield env.timeout(0.25)
        yield env.timeout(0.75)
        server.put(high)

    env.process(arrival())
    env.run()

    assert server.out.received == [(1, first), (2, high), (3, low)]


@pytest.mark.parametrize("zero_downstream_buffer", [False, True])
def test_class_queues_exclude_service_and_retained_downstream_packets(
    zero_downstream_buffer,
):
    env = simpy.Environment()
    server = server_with_sink(
        env,
        {"gold": 7, "silver": 7},
        flow_classes=lambda p: "gold" if p.flow_id in (10, 11) else "silver",
        zero_downstream_buffer=zero_downstream_buffer,
    )
    first, second, third = packet(0, 10), packet(1, 11, 40), packet(2, 20, 30)
    for item in (first, second, third):
        server.put(item)
    env.run(until=0.25)

    assert server.packet_in_service() is first
    assert server.size("gold") == 1
    assert server.byte_size("gold") == 40
    assert server.size("silver") == 1
    assert server.byte_size("silver") == 30
    assert server.total_packets() == 2
    assert set(server.all_flows()) == {"gold", "silver"}
    assert server.size("unknown") == server.byte_size("unknown") == 0

    env.run()
    assert [item for _, item in server.out.received] == [first, second, third]
    assert [time for time, _ in server.out.received] == pytest.approx([1, 1.4, 1.7])
    assert server.packet_in_service() is None
    assert server.size("gold") == server.byte_size("gold") == 0
    assert server.size("silver") == server.byte_size("silver") == 0
    assert server.total_packets() == 0
    if zero_downstream_buffer:
        assert server.stores[7].items == [first, second, third]


def test_monitor_adds_service_once_and_counts_flow_queue_separately():
    env = simpy.Environment()
    server = server_with_sink(env, {10: 7})
    waiting = ServerMonitor(env, server, lambda: 0.5)
    total = ServerMonitor(env, server, lambda: 0.5, pkt_in_service_included=True)
    server.put(packet(0, 10))
    server.put(packet(1, 10, 40))
    env.run(until=0.75)

    assert waiting.sizes[10] == [1]
    assert waiting.byte_sizes[10] == [40]
    assert total.sizes[10] == [2]
    assert total.byte_sizes[10] == [140]


def test_zero_buffer_releases_selected_packet_identity_from_a_shared_store():
    env = simpy.Environment()
    server = server_with_sink(env, [1, 9], zero_buffer=True)
    upstream = simpy.Store(env)
    low, high = packet(0), packet(1, 1)
    released = []

    def release(item):
        # Reordering service must not release another resident upstream packet.
        assert item not in upstream.items
        released.append((env.now, item, list(upstream.items)))

    for item in (low, high):
        upstream.put(item)
        server.put(item, upstream_update=release, upstream_store=upstream)
    env.run()

    assert released == [(1, high, [low]), (2, low, [])]
    assert server.out.received == [(1, high), (2, low)]
    assert not server.upstream_stores
    assert not server.upstream_updates


def test_zero_buffer_standalone_input_does_not_require_upstream_hooks():
    env = simpy.Environment()
    server = server_with_sink(env, [1], zero_buffer=True)
    item = packet(0)
    server.put(item)
    env.run()
    assert server.out.received == [(1, item)]


def test_downstream_release_propagates_only_when_the_packet_is_pulled():
    env = simpy.Environment()
    server = server_with_sink(
        env, [1, 9], zero_buffer=True, zero_downstream_buffer=True
    )
    upstream = simpy.Store(env)
    low, high = packet(0), packet(1, 1)
    released = []

    def release(item):
        assert item not in upstream.items
        released.append(item)

    for item in (low, high):
        upstream.put(item)
        server.put(item, upstream_update=release, upstream_store=upstream)
    env.run()

    assert released == []
    assert upstream.items == [low, high]
    assert server.out.received == [(1, high), (2, low)]
    for item, update, store in server.out.handoffs:
        assert store.get().value is item
        update(item)
    assert released == [high, low]
    assert not upstream.items
    assert not server.upstream_stores
    assert not server.upstream_updates


def test_idle_wakeup_does_not_leave_eligible_packets_without_service():
    env = simpy.Environment()
    server = server_with_sink(env, [1, 9])
    first, low, high = packet(0), packet(1), packet(2, 1)
    server.put(first)
    env.run(until=2)
    assert server.packet_in_service() is None
    server.put(low)
    server.put(high)
    env.run()
    assert server.out.received == [(1, first), (3, high), (4, low)]


def test_wakeup_storage_stays_bounded_when_arrivals_overlap_each_service():
    env = simpy.Environment()
    server = server_with_sink(env, [1])
    packets = [packet(i) for i in range(5)]
    server.put(packets[0])
    token_counts = []

    def arrivals():
        yield env.timeout(0.5)
        for item in packets[1:]:
            server.put(item)
            token_counts.append(len(server.packets_available.items))
            yield env.timeout(1)

    env.process(arrivals())
    env.run()
    assert server.out.received == [(i + 1, item) for i, item in enumerate(packets)]
    assert max(token_counts) <= 1
    assert not server.packets_available.items


def test_synchronous_downstream_observes_completed_service_state():
    env = simpy.Environment()
    server = server_with_sink(env, [1])
    first, next_packet = packet(0), packet(1, size=40)
    observations = []

    class ReentrantSink:
        def put(self, item):
            observations.append((env.now, item, server.packet_in_service()))
            if item is first:
                server.put(next_packet)

    server.out = ReentrantSink()
    server.put(first)
    env.run()
    assert observations == [(1, first, None), (1.4, next_packet, None)]
