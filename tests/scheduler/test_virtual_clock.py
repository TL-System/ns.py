"""Virtual Clock orders packets by seconds of reserved-rate service."""

import pytest
import simpy

from ns.packet.packet import Packet
from ns.scheduler.monitor import ServerMonitor
from ns.scheduler.virtual_clock import VirtualClockServer


class CaptureSink:
    def __init__(self, env):
        self.env = env
        self.received = []
        self.handoffs = []

    def put(self, packet, upstream_update=None, upstream_store=None):
        self.received.append((self.env.now, packet))
        self.handoffs.append((packet, upstream_update, upstream_store))


def packet(packet_id, flow_id=0, size=100):
    # Generation time is deliberately different from later queue arrival times.
    return Packet(0, size, packet_id, flow_id=flow_id)


def make_server(vticks, **kwargs):
    env = simpy.Environment()
    # 800 bits/second makes each 100-byte packet take one second on the link.
    server = VirtualClockServer(env, rate=800, vticks=vticks, **kwargs)
    server.out = CaptureSink(env)
    return env, server


def assert_departures(server, expected_packets, expected_times):
    assert [item for _, item in server.out.received] == expected_packets
    assert [time for time, _ in server.out.received] == pytest.approx(expected_times)


@pytest.mark.parametrize("vticks", [[1 / 8000, 1 / 4000], {0: 1 / 8000, 1: 1 / 4000}])
def test_tag_uses_packet_bits_and_reserved_rate(vticks):
    env, server = make_server(vticks)
    large, small = packet(0, 0, 1000), packet(1, 1, 100)
    server.put(large)
    server.put(small)
    # Reserved-rate finish tags are 1 and 0.2 seconds. The smaller vtick alone
    # cannot rank variable-size packets: link service still takes 1 then 10 s.
    env.run()
    assert_departures(server, [small, large], [1, 11])
    assert server.aux_vc == pytest.approx({0: 1, 1: 0.2})
    assert server.v_clocks == pytest.approx({0: 1, 1: 0.2})


def test_two_flows_share_one_class_clock_and_keep_class_fifo():
    env, server = make_server(
        {"a": 1 / 8000, "b": 1 / 8000},
        flow_classes=lambda p: "a" if p.flow_id in (10, 11) else "b",
    )
    first, second, other = packet(0, 10, 500), packet(1, 11), packet(2, 20, 900)
    for item in (first, second, other):
        server.put(item)
    # The two class-a flows consume successive tags 0.5 and 0.6; class b is 0.9.
    env.run()
    assert_departures(server, [first, second, other], [5, 6, 15])
    assert server.aux_vc == pytest.approx({"a": 0.6, "b": 0.9})
    assert set(server.all_flows()) == {"a", "b"}


def test_equal_tags_keep_admission_order_across_classes():
    env, server = make_server([1 / 800, 1 / 1600, 1 / 400])
    packets = [packet(0, 0), packet(1, 1, 200), packet(2, 2, 50)]
    for item in packets:
        server.put(item)
    # Each tag is exactly one second, despite unequal packet sizes and vticks.
    env.run()
    assert_departures(server, packets, [1, 3, 3.5])


def test_idle_arrival_floors_auxiliary_clock_without_resetting_monitoring_clock():
    env, server = make_server([1 / 8000])
    first, second, later = packet(0, size=1000), packet(1, size=500), packet(2, size=250)

    def arrivals():
        yield env.timeout(5)
        server.put(first)
        server.put(second)
        yield env.timeout(25)
        server.put(later)

    env.process(arrivals())
    env.run()
    assert_departures(server, [first, second, later], [15, 20, 32.5])
    # Initialize at 5 s, then accumulate 1 + 0.5 + 0.25 s of requested service.
    # The scheduling clock instead catches up to the later arrival at 30 s.
    assert server.v_clocks[0] == pytest.approx(6.75)
    assert server.aux_vc[0] == pytest.approx(30.25)


def test_empty_queue_does_not_erase_a_clock_still_ahead_of_real_time():
    env, server = make_server([1 / 8])
    first, later = packet(0), packet(1, size=50)
    server.put(first)
    env.run(until=2)
    assert server.packet_in_service() is None
    server.put(later)
    env.run()
    # The first tag was 100 s; emptying the physical queue does not forgive it.
    assert server.aux_vc[0] == 150
    assert server.v_clocks[0] == 150
    assert_departures(server, [first, later], [1, 2.5])


def test_large_future_tag_does_not_delay_an_otherwise_idle_link():
    env, server = make_server([1])
    item = packet(0)
    server.put(item)
    env.run()
    # A tag ranks work; it is not an eligibility time or a shaping deadline.
    assert_departures(server, [item], [1])


def test_later_smaller_tag_waits_for_current_packet_then_wins_selection():
    env, server = make_server([1 / 8, 1 / 8000])
    first, waiting, later = packet(0), packet(1), packet(2, 1, 50)
    server.put(first)
    server.put(waiting)

    def arrival():
        yield env.timeout(0.25)
        server.put(later)

    env.process(arrival())
    env.run()
    assert_departures(server, [first, later, waiting], [1, 1.5, 2.5])


def test_arrival_at_completion_joins_next_tag_selection():
    env, server = make_server([1 / 8, 1 / 8000])
    first, waiting, later = packet(0), packet(1), packet(2, 1)
    server.put(first)
    server.put(waiting)

    def arrival():
        # Create this arrival timeout after the timeout for current service.
        yield env.timeout(0.25)
        yield env.timeout(0.75)
        server.put(later)

    env.process(arrival())
    env.run()
    assert_departures(server, [first, later, waiting], [1, 2, 3])


def test_idle_wakeup_selects_from_all_arrivals_at_that_time():
    env, server = make_server([1 / 8, 1 / 8000])
    first, large_tag, small_tag = packet(0), packet(1), packet(2, 1)
    server.put(first)
    env.run(until=2)
    server.put(large_tag)

    def same_time_arrival():
        yield env.timeout(0)
        server.put(small_tag)

    env.process(same_time_arrival())
    env.run()
    assert_departures(server, [first, small_tag, large_tag], [1, 3, 4])


@pytest.mark.parametrize("zero_downstream_buffer", [False, True])
def test_queue_counts_exclude_local_service_and_downstream_retention(
    zero_downstream_buffer,
):
    env, server = make_server(
        {"a": 1 / 8},
        flow_classes=lambda p: "a",
        zero_downstream_buffer=zero_downstream_buffer,
    )
    first, waiting = packet(0, 10), packet(1, 11, 40)
    server.put(first)
    server.put(waiting)
    env.run(until=0.25)
    assert server.packet_in_service() is first
    assert server.size("a") == 1
    assert server.byte_size("a") == 40
    assert server.size("unknown") == server.byte_size("unknown") == 0
    env.run()
    assert_departures(server, [first, waiting], [1, 1.4])
    assert server.size("a") == server.byte_size("a") == 0
    assert server.packet_in_service() is None
    assert server.packets_received == 2
    assert server.packets_dropped == 0
    if zero_downstream_buffer:
        assert [entry[2] for entry in server.store.items] == [first, waiting]


def test_monitor_adds_current_packet_once_to_waiting_telemetry():
    env, server = make_server([1 / 8])
    queued = ServerMonitor(env, server, lambda: 0.5)
    total = ServerMonitor(env, server, lambda: 0.5, pkt_in_service_included=True)
    server.put(packet(0))
    server.put(packet(1, size=40))
    env.run(until=0.75)
    assert queued.sizes[0] == [1]
    assert queued.byte_sizes[0] == [40]
    assert total.sizes[0] == [2]
    assert total.byte_sizes[0] == [140]


def test_synchronous_forwarding_observes_completed_service():
    env, server = make_server([1 / 8])
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


def test_zero_buffer_standalone_input_does_not_require_optional_upstream_hooks():
    env, server = make_server([1 / 8], zero_buffer=True)
    item = packet(0)
    server.put(item)
    env.run()
    assert_departures(server, [item], [1])


@pytest.mark.parametrize("zero_downstream_buffer", [False, True])
def test_upstream_callback_is_released_at_completion_or_downstream_pull(
    zero_downstream_buffer,
):
    env, server = make_server(
        [1 / 8], zero_buffer=True, zero_downstream_buffer=zero_downstream_buffer
    )
    upstream = simpy.Store(env)
    item = packet(0)
    upstream.put(item)
    released = []

    def release(pulled):
        assert pulled is item
        assert item not in upstream.items
        released.append((env.now, server.packet_in_service()))

    server.put(item, upstream_update=release, upstream_store=upstream)
    env.run(until=0.25)
    assert released == []
    env.run(until=2)
    if zero_downstream_buffer:
        assert released == []
        assert upstream.items == [item]
        forwarded, update, store = server.out.handoffs[0]
        assert forwarded is item
        assert store is server.store
        assert store.get().value is item
        update(item)
        assert released == [(2, None)]
    else:
        assert released == [(1, None)]
    assert not server.upstream_stores
    assert not server.upstream_updates
    assert_departures(server, [item], [1])


@pytest.mark.parametrize("bad_vtick", [0, -1, float("inf"), float("nan")])
def test_reserved_bit_time_must_be_positive_and_finite(bad_vtick):
    with pytest.raises(ValueError, match="vtick"):
        make_server([bad_vtick])


def test_unknown_class_is_rejected_without_partial_admission():
    env, server = make_server({"a": 1 / 8}, flow_classes=lambda p: "missing")
    with pytest.raises(KeyError):
        server.put(packet(0))
    env.run()
    assert server.packets_received == 0
    assert list(server.all_flows()) == []
    assert server.flow_queue_count == {"a": 0}
    assert server.store.items == []
