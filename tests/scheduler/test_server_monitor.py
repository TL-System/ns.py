"""Scheduler monitor samples waiting work separately from local service."""

import pytest
import simpy

from ns.packet.packet import Packet
from ns.packet.sink import PacketSink
from ns.port.port import Port
from ns.scheduler.drr import DRRServer
from ns.scheduler.monitor import ServerMonitor
from ns.scheduler.sp import SPServer
from ns.scheduler.virtual_clock import VirtualClockServer
from ns.scheduler.wfq import WFQServer


@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf")])
def test_invalid_sampling_interval_fails_without_livelock(interval):
    env = simpy.Environment()
    ServerMonitor(env, SPServer(env, 800, {0: 1}), lambda: interval)
    with pytest.raises(ValueError, match="positive and finite"):
        for _ in range(5):
            env.step()


@pytest.mark.parametrize("kind", [SPServer, DRRServer, WFQServer, VirtualClockServer])
def test_class_mapping_and_downstream_retention_are_counted_once(kind):
    env = simpy.Environment()
    port = Port(env, 0, qlimit=2, zero_downstream_buffer=True)
    scheduler = kind(
        env, 80000, {"shared": 1}, flow_classes=lambda p: "shared",
        zero_buffer=True, zero_downstream_buffer=True,
    )
    downstream = SPServer(
        env, 800, {"other": 1}, flow_classes=lambda p: "other", zero_buffer=True
    )
    downstream.out = PacketSink(env)
    scheduler.out = downstream
    port.out = scheduler
    waiting = ServerMonitor(env, scheduler, lambda: 0.006)
    inclusive = ServerMonitor(env, scheduler, lambda: 0.006, True)
    downstream_total = ServerMonitor(env, downstream, lambda: 0.006, True)
    port.put(Packet(0, 100, 0, flow_id=17))
    port.put(Packet(0, 40, 1, flow_id=23))
    env.run(until=0.019)
    assert waiting.sizes["shared"] == [1, 0, 0]
    assert waiting.byte_sizes["shared"] == [40, 0, 0]
    assert inclusive.sizes["shared"] == [2, 1, 0]
    assert inclusive.byte_sizes["shared"] == [140, 40, 0]
    # Upper service completed at .01 and .014 s, but lower service still owns
    # both packets. Scheduler telemetry excludes retention; port admission does
    # include it, so the same physical packets cannot acquire capacity twice.
    assert port.byte_size == 140
    assert downstream_total.sizes["other"] == [1, 2]
    assert downstream_total.byte_sizes["other"] == [100, 140]
    env.run(until=1.5)
    assert port.byte_size == 0
    assert port._packets_removed == 2
    assert inclusive.sizes["shared"][-1] == 0
    assert downstream_total.sizes["other"][-1] == 0
