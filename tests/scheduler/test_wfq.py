"""WFQ selection and timing from independently calculated finish tags."""

import pytest
import simpy

from ns.packet.packet import Packet
from ns.scheduler.wfq import WFQServer


class CaptureSink:
    def __init__(self, env):
        self.env = env
        self.observed = []

    def put(self, packet, **kwargs):
        self.observed.append((packet.packet_id, self.env.now))


def make_server(weights, **kwargs):
    env = simpy.Environment()
    # Eight bits/s makes a byte take one second, keeping hand calculations clear.
    server = WFQServer(env, rate=8, weights=weights, **kwargs)
    sink = CaptureSink(env)
    server.out = sink
    return env, server, sink


def packet(packet_id, flow_id, size=1):
    return Packet(0, size, packet_id, flow_id=flow_id)


def arrive(env, server, at, *packets):
    def send():
        yield env.timeout(at - env.now)
        for item in packets:
            server.put(item)

    env.process(send())


def assert_departures(sink, ids, times):
    assert [identity for identity, _ in sink.observed] == ids
    assert [time for _, time in sink.observed] == pytest.approx(times)


def test_first_packet_gets_its_weighted_finish_tag():
    env, server, sink = make_server([1, 8])
    # Tags are 8 and 1/8, including the first admission to an idle server.
    server.put(packet(0, 0, 8))
    server.put(packet(1, 1))

    env.run()

    assert_departures(sink, [1, 0], [1, 9])


def test_equal_tags_keep_arrival_order_and_class_fifo():
    env, server, sink = make_server(
        {"a": 1, "b": 2},
        flow_classes=lambda p: "a" if p.flow_id < 2 else "b",
    )
    # Class a shares one finish history across two flows. All first-round tags
    # equal 1; their second-round tags equal 2, with admission-order ties.
    for item in [packet(0, 0), packet(1, 2, 2), packet(2, 1), packet(3, 3, 2)]:
        server.put(item)

    env.run()

    assert_departures(sink, [0, 1, 2, 3], [1, 3, 4, 6])


def test_idle_restart_assigns_fresh_tags():
    env, server, sink = make_server([1, 8])
    server.put(packet(0, 0))
    arrive(env, server, 10, packet(1, 0, 8), packet(2, 1))

    env.run()

    assert_departures(sink, [0, 2, 1], [1, 11, 19])
    assert server.vtime == 0
    assert not server.active_set


def test_service_is_nonpreemptive_and_selection_uses_queued_tags():
    env, server, sink = make_server([1, 8])
    server.put(packet(0, 0, 8))
    # A smaller-tag arrival cannot displace the packet already being serialized.
    arrive(env, server, 1, packet(1, 0), packet(2, 1))

    env.run()

    assert_departures(sink, [0, 2, 1], [8, 9, 10])


def test_positive_lightweight_class_receives_service_amid_heavy_backlog():
    env, server, sink = make_server([1, 8])
    for identity in range(16):
        server.put(packet(identity, 1))
    server.put(packet(16, 0))

    env.run()

    # The heavy class's eighth packet ties the light class's first tag at 1;
    # the heavy packet arrived first, so the light packet is served ninth.
    assert_departures(
        sink, list(range(8)) + [16] + list(range(8, 16)), list(range(1, 18))
    )


@pytest.mark.parametrize("zero_downstream_buffer", [False, True])
def test_queue_accessors_exclude_packet_in_service(zero_downstream_buffer):
    env, server, sink = make_server(
        {"one": 1}, flow_classes=lambda p: "one",
        zero_downstream_buffer=zero_downstream_buffer,
    )
    first = packet(0, 7, 2)
    server.put(first)
    server.put(packet(1, 8))

    env.run(until=0.5)

    assert server.packet_in_service() is first
    assert server.size("one") == 1
    assert server.byte_size("one") == 1
    assert server.size("missing") == server.byte_size("missing") == 0
    assert server.total_packets() == 1
    assert server.all_flows() == ["one"]
    env.run()
    assert_departures(sink, [0, 1], [2, 3])
    assert server.size("one") == server.byte_size("one") == 0
    assert server.total_packets() == 0
    assert server.packet_in_service() is None
    if zero_downstream_buffer:
        # Retained ownership is distinct from locally active WFQ traffic.
        assert len(server.store.items) == 2
        assert not server.active_set
        assert server.vtime == 0


def test_virtual_clock_counts_queued_and_in_service_classes_until_completion():
    env, server, sink = make_server([1, 1, 1, 1, 1])
    for identity, size in enumerate([10, 100, 13, 14]):
        server.put(packet(identity, identity, size))
    arrive(env, server, 15, packet(4, 4, 10))

    env.run(until=15.5)

    # Days drops class 0 at its physical completion (10 seconds). Class 2
    # remains active while in service, so V(15) = 10/4 + 5/3 = 25/6.
    # New tag 25/6 + 10 = 85/6 exceeds class 3's tag 14. A fluid GPS
    # reference instead gives 15/4 + 10 = 55/4 and chooses class 4 first.
    assert server.vtime == pytest.approx(25 / 6)
    assert server.finish_times[4] == pytest.approx(85 / 6)
    assert server.active_set == {1, 2, 3, 4}
    assert server.size(2) == 0
    assert server.packet_in_service().flow_id == 2
    env.run()
    assert_departures(sink, [0, 2, 3, 4, 1], [10, 23, 37, 47, 147])


def test_virtual_clock_uses_weights_before_activating_an_arriving_class():
    env, server, sink = make_server([1, 3, 2])
    server.put(packet(0, 0, 4))
    server.put(packet(1, 1, 30))
    arrive(env, server, 2, packet(2, 2))

    env.run(until=2.5)

    # The first two tags are 4 and 10. During class 0's service their
    # weights sum to 4; the arriving class's weight joins only after tagging.
    assert server.vtime == pytest.approx(2 / 4)
    assert server.finish_times[2] == pytest.approx(2 / 4 + 1 / 2)
    assert server.active_set == {0, 1, 2}
    env.run()
    assert_departures(sink, [0, 2, 1], [4, 5, 35])


def test_arrival_at_completion_joins_next_selection():
    env, server, sink = make_server([1, 8])
    server.put(packet(0, 0, 8))
    server.put(packet(1, 0))
    env.run(until=0.5)
    # Insert this arrival timeout after the service completion timeout.
    arrive(env, server, 8, packet(2, 1))

    env.run()

    assert_departures(sink, [0, 2, 1], [8, 9, 10])


def test_idle_wakeup_selects_from_all_arrivals_at_that_time():
    env, server, sink = make_server([1, 8])
    server.put(packet(0, 0))
    env.run(until=2)
    server.put(packet(1, 0, 8))
    arrive(env, server, 2, packet(2, 1))

    env.run()

    assert_departures(sink, [0, 2, 1], [1, 3, 11])


def test_synchronous_forwarding_observes_completed_service_and_can_reenter():
    env, server, _ = make_server([1])
    observations = []
    first, later = packet(0, 0), packet(1, 0, 2)

    class ReentrantSink:
        def put(self, item):
            observations.append((item, env.now, server.packet_in_service()))
            if item is first:
                server.put(later)

    server.out = ReentrantSink()
    server.put(first)
    env.run()

    assert observations == [(first, 1, None), (later, 3, None)]
    assert not server.active_set
    assert server.vtime == 0


def test_zero_buffer_input_can_omit_optional_upstream_hooks():
    env, server, sink = make_server([1], zero_buffer=True)
    server.put(packet(0, 0))
    env.run()
    assert_departures(sink, [0], [1])


@pytest.mark.parametrize("class_id", ["missing", -1])
def test_unknown_class_fails_before_any_admission_accounting(class_id):
    env, server, sink = make_server([1], flow_classes=lambda p: class_id)
    with pytest.raises(KeyError):
        server.put(packet(0, 0))
    env.run()
    assert server.packets_received == 0
    assert not server.all_flows()
    assert server.flow_queue_count == {0: 0}
    assert not server.active_set
    assert not server.store.items
    assert not sink.observed


@pytest.mark.parametrize(
    "weights", [[0], [-1], [float("nan")], [float("inf")], [], {}, {"a": 0}, (1,)]
)
def test_weights_must_be_nonempty_finite_positive(weights):
    with pytest.raises(ValueError):
        WFQServer(simpy.Environment(), rate=8, weights=weights)


@pytest.mark.parametrize("rate", [0, -8, float("nan"), float("inf")])
def test_link_rate_must_be_positive(rate):
    with pytest.raises(ValueError):
        WFQServer(simpy.Environment(), rate=rate, weights=[1])
