"""Copies describe one logical packet but own independent path metadata."""

import pytest
import simpy

from ns.packet.packet import Packet
from ns.packet.sink import PacketSink
from ns.port.port import Port
from ns.utils.splitter import NWaySplitter, Splitter


@pytest.mark.parametrize("kind", ["two", "three"])
def test_splitter_snapshots_all_branches_before_synchronous_forwarding(kind):
    seen = []

    class Branch:
        def __init__(self, name):
            self.name = name

        def put(self, packet):
            seen.append((packet, packet.perhop_time.copy(), packet.prio["path"][:]))
            packet.perhop_time[self.name] = 1
            packet.prio["path"].append(self.name)
            packet.color = self.name

    packet = Packet(0, 100, 42, flow_id="logical", payload=b"opaque")
    packet.perhop_time["before"] = 0
    packet.prio["path"] = ["before"]
    splitter = Splitter() if kind == "two" else NWaySplitter(3)
    branches = [Branch(str(i)) for i in range(2 if kind == "two" else 3)]
    if isinstance(splitter, Splitter):
        splitter.out1, splitter.out2 = branches
    else:
        splitter.outs = branches
    splitter.put(packet)
    assert seen[0][0] is packet
    assert len({id(item) for item, _, _ in seen}) == len(branches)
    for item, hops, priorities in seen:
        assert (item.packet_id, item.flow_id, item.payload) == (
            42, "logical", b"opaque"
        )
        assert hops == {"before": 0}
        assert priorities == ["before"]
        assert len(item.perhop_time) == 2
        assert len(item.prio["path"]) == 2


def test_splitter_composes_with_distinct_link_times_without_cross_path_hops():
    env = simpy.Environment()
    splitter = Splitter()
    slow, fast = Port(env, 800, element_id="slow"), Port(env, 1600, element_id="fast")
    sinks = [PacketSink(env), PacketSink(env)]
    slow.out, fast.out = sinks
    splitter.out1, splitter.out2 = slow, fast
    packet = Packet(0, 100, 0)
    splitter.put(packet)
    env.run()
    assert sinks[0].arrivals[0] == [1]
    assert sinks[1].arrivals[0] == [0.5]
    assert sinks[0].perhop_times[0] == [{"slow": 0}]
    assert sinks[1].perhop_times[0] == [{"fast": 0}]


def test_nway_splitter_can_leave_unused_branches_disconnected():
    env = simpy.Environment()
    splitter = NWaySplitter(3)
    sink = PacketSink(env)
    splitter.outs[1] = sink
    splitter.put(Packet(0, 100, 0))
    assert sink.packets_received[0] == 1
