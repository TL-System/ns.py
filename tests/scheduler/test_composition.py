"""Identity, retained ownership, and telemetry across composed schedulers."""

import pytest
import simpy

from ns.packet.packet import Packet
from ns.port.port import Port
from ns.scheduler.drr import DRRServer
from ns.scheduler.monitor import ServerMonitor
from ns.scheduler.sp import SPServer
from ns.scheduler.virtual_clock import VirtualClockServer
from ns.scheduler.wfq import WFQServer
from ns.switch.switch import FairPacketSwitch, SimplePacketSwitch
from ns.utils.taggedstore import TaggedStore


KINDS = ["SP", "DRR", "WFQ", "VirtualClock"]
SERVER_TYPES = {
    "SP": SPServer,
    "DRR": DRRServer,
    "WFQ": WFQServer,
    "VirtualClock": VirtualClockServer,
}


class CaptureSink:
    def __init__(self, env):
        self.env = env
        self.observed = []

    def put(self, packet, **kwargs):
        self.observed.append((packet, self.env.now))


def packet(identity, flow_id, size=100):
    return Packet(0, size, identity, flow_id=flow_id)


def server(env, kind, classes, rate=800, **kwargs):
    # Parameters affect the chosen algorithm only; all expose the same hooks.
    if kind == "SP":
        return SPServer(env, rate, classes, **kwargs)
    if kind == "VirtualClock":
        return VirtualClockServer(env, rate, classes, **kwargs)
    return SERVER_TYPES[kind](env, rate, classes, **kwargs)


def retained(server):
    """Return the original objects still owned by a scheduler's physical store."""
    if hasattr(server, "store"):
        return {item[2] for item in server.store.items}
    return {item for store in server.stores.values() for item in store.items}


@pytest.mark.parametrize("upstream_kind", KINDS)
@pytest.mark.parametrize("downstream_kind", KINDS)
def test_hierarchy_releases_selected_identity_through_different_class_maps(
    upstream_kind, downstream_kind
):
    env = simpy.Environment()
    buffer = Port(env, 0, qlimit=3, zero_downstream_buffer=True)
    upstream = server(
        env, upstream_kind,
        {"group": 1 / 800 if upstream_kind == "VirtualClock" else 1},
        rate=800000,
        flow_classes=lambda p: "group",
        zero_buffer=True,
        zero_downstream_buffer=True,
    )
    # Low's 2000 bytes exceed DRR's fixed quantum and give it a large finish
    # tag in both heap schedulers. SP gives high an explicitly larger priority.
    classes = {"blocker": 1, "low": 1, "high": 2}
    if downstream_kind == "VirtualClock":
        classes = {"blocker": 1 / 800, "low": 1 / 800, "high": 1 / 8000}
    downstream = server(
        env, downstream_kind, classes,
        flow_classes=lambda p: ["blocker", "low", "high"][p.flow_id],
        zero_buffer=True,
    )
    sink = CaptureSink(env)
    buffer.out = upstream
    upstream.out = downstream
    downstream.out = sink
    first, low, high = packet(0, 0), packet(1, 1, 2000), packet(2, 2)
    releases = []
    original_update = buffer.update

    def release(item):
        original_update(item)
        releases.append(
            (item, env.now, list(buffer.store.items), retained(upstream),
             buffer.byte_size)
        )
        # Hooks must disappear before a callback can synchronously revisit them.
        assert item not in upstream.upstream_stores
        assert item not in downstream.upstream_stores

    buffer.update = release
    for item in [first, low, high]:
        buffer.put(item)

    env.run(until=0.1)
    assert upstream.size("group") == upstream.byte_size("group") == 0
    assert upstream.packet_in_service() is None
    assert retained(upstream) == {first, low, high}
    assert buffer.byte_size == 2200
    # Local service has completed upstream, but downstream retains all capacity.
    rejected = packet(3, 0)
    assert buffer.put(rejected) is None
    assert buffer.packets_dropped == 1
    env.run(until=23)

    expected = [first, high, low]
    assert [item for item, _ in sink.observed] == expected
    # Upstream's first packet takes .001 s; downstream takes 1, 1, and 20 s.
    assert [time for _, time in sink.observed] == pytest.approx(
        [1.001, 2.001, 22.001]
    )
    assert [item for item, *_ in releases] == expected
    assert [time for _, time, *_ in releases] == pytest.approx(
        [1.001, 2.001, 22.001]
    )
    assert [items for _, _, items, _, _ in releases] == [[low, high], [low], []]
    assert [items for _, _, _, items, _ in releases] == [
        {low, high}, {low}, set()
    ]
    assert [size for *_, size in releases] == [2100, 2000, 0]
    assert buffer._packets_removed == 3
    assert buffer.packets_received == 4
    assert not buffer.store.items
    for element in [upstream, downstream]:
        assert not element.upstream_stores
        assert not element.upstream_updates
        assert not retained(element)
        assert all(element.size(cls) == 0 for cls in element.all_flows())
        assert all(element.byte_size(cls) == 0 for cls in element.all_flows())


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("tagged", [False, True], ids=["fifo", "tagged"])
def test_release_preserves_other_objects_and_wakes_bounded_pending_put(kind, tagged):
    env = simpy.Environment()
    upstream = TaggedStore(env, capacity=3) if tagged else simpy.Store(env, capacity=3)
    first, selected, third, pending = [packet(7, 0) for _ in range(4)]
    # Same packet_id and class on distinct objects catches value-based removal.
    puts = [
        upstream.put((tag, item) if tagged else item)
        for tag, item in [(1, first), (1, selected), (1, third), (0, pending)]
    ]
    element = server(
        env, kind, {0: 1}, zero_buffer=True, zero_downstream_buffer=True
    )
    element.out = CaptureSink(env)
    callbacks = []

    def release(item):
        assert item not in element.upstream_stores
        assert item not in element.upstream_updates
        callbacks.append(item)

    element.put(selected, upstream_update=release, upstream_store=upstream)
    assert [put.triggered for put in puts] == [True, True, True, False]
    element.update(selected)
    # Repeated release cannot remove a second object or charge a second callback.
    element.update(selected)
    env.run(until=0.01)
    assert callbacks == [selected]
    assert puts[-1].triggered
    observed = [upstream.get().value for _ in range(3)]
    assert observed == ([pending, first, third] if tagged else [first, third, pending])
    assert not upstream.items


def test_targeted_tagged_get_waits_for_its_object_without_reserving_another():
    env = simpy.Environment()
    upstream = TaggedStore(env)
    first, selected, last = packet(0, 0), packet(1, 0), packet(2, 0)
    requested = upstream.get(selected)
    upstream.put((1, first))
    upstream.put((1, last))
    env.run()
    assert not requested.triggered
    ordinary = upstream.get()
    assert ordinary.triggered
    assert ordinary.value is first
    upstream.put((10, selected))
    env.run(until=requested)
    assert requested.value is selected
    assert upstream.get().value is last


@pytest.mark.parametrize("kind", KINDS)
def test_zero_buffer_accepts_direct_input_without_upstream_hooks(kind):
    env = simpy.Environment()
    element = server(env, kind, {0: 1}, zero_buffer=True)
    element.out = CaptureSink(env)
    original = packet(0, 0)
    element.put(original)
    env.run()
    assert element.out.observed == [(original, 1)]
    assert not element.upstream_stores
    assert not element.upstream_updates


@pytest.mark.parametrize("kind", ["SP", "DRR", "VirtualClock"])
def test_monitor_includes_service_once_under_mapped_classes(kind):
    env = simpy.Environment()
    element = server(
        env, kind, {"shared": 1}, flow_classes=lambda p: "shared"
    )
    element.out = CaptureSink(env)
    waiting = ServerMonitor(env, element, lambda: 0.25)
    inclusive = ServerMonitor(env, element, lambda: 0.25, True)
    element.put(packet(0, 17))
    element.put(packet(1, 23, 40))
    env.run(until=0.3)
    assert waiting.sizes["shared"] == [1]
    assert waiting.byte_sizes["shared"] == [40]
    assert inclusive.sizes["shared"] == [2]
    assert inclusive.byte_sizes["shared"] == [140]
    env.run(until=1.51)
    assert inclusive.sizes["shared"][-1] == 0
    assert inclusive.byte_sizes["shared"][-1] == 0


@pytest.mark.parametrize("kind", KINDS)
def test_fair_switch_selects_scheduler_and_retains_egress_capacity(kind):
    env = simpy.Environment()
    switch = FairPacketSwitch(
        env, 2, 800, 2, {"shared": 1}, kind,
        flow_classes=lambda p: "shared", element_id="switch",
    )
    sinks = [CaptureSink(env), CaptureSink(env)]
    for index, scheduler in enumerate(switch.ports):
        assert isinstance(scheduler, SERVER_TYPES[kind])
        assert scheduler.zero_buffer
        assert switch.egress_ports[index].zero_downstream_buffer
        assert switch.egress_ports[index].out is scheduler
        scheduler.out = sinks[index]
    switch.demux.fib = {10: 0, 11: 1}
    first, second, dropped, other = [
        packet(0, 10), packet(1, 10, 40), packet(2, 10), packet(3, 11, 50)
    ]
    for item in [first, second, dropped, other]:
        switch.put(item)
    env.run(until=0.3)
    assert switch.egress_ports[0].byte_size == 140
    assert switch.egress_ports[0].packets_dropped == 1
    assert switch.egress_ports[1].byte_size == 50
    assert first.perhop_time["switch_0"] == 0
    assert other.perhop_time["switch_1"] == 0
    env.run(until=2)
    assert sinks[0].observed == [(first, 1), (second, 1.4)]
    assert sinks[1].observed == [(other, 0.5)]
    assert all(port.byte_size == 0 for port in switch.egress_ports)
    assert [port._packets_removed for port in switch.egress_ports] == [2, 1]


def test_simple_switch_routes_to_fifo_ports():
    env = simpy.Environment()
    switch = SimplePacketSwitch(env, 2, 800, 1)
    sinks = [CaptureSink(env), CaptureSink(env)]
    for port, sink in zip(switch.ports, sinks):
        port.out = sink
    switch.demux.fib = {0: 0, 1: 1}
    first, dropped, other = packet(0, 0), packet(1, 0), packet(2, 1, 40)
    for item in [first, dropped, other]:
        switch.put(item)
    env.run(until=2)
    assert sinks[0].observed == [(first, 1)]
    assert sinks[1].observed == [(other, 0.4)]
    assert switch.ports[0].packets_dropped == 1


def test_fair_switch_rejects_unknown_scheduler():
    with pytest.raises(ValueError, match="Scheduler type"):
        FairPacketSwitch(simpy.Environment(), 1, 800, 1, [1], "unknown")
