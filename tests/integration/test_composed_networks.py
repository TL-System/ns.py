"""Small networks with byte, identity, timing, and final-drain oracles."""

import pytest
import simpy

from ns.flow.cc import TCPReno
from ns.flow.flow import Flow
from ns.packet.packet import Packet
from ns.packet.tcp_generator import TCPPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.port.monitor import PortMonitor
from ns.port.port import Port
from ns.port.wire import Wire
from ns.scheduler.drr import DRRServer
from ns.scheduler.monitor import ServerMonitor
from ns.scheduler.sp import SPServer
from ns.shaper.token_bucket import TokenBucketShaper


class Capture:
    """Observe original objects at a connection without changing the handoff."""

    def __init__(self, env, out=None):
        self.env = env
        self.out = out
        self.items = []

    def put(self, packet, **kwargs):
        self.items.append((self.env.now, packet))
        if self.out is not None:
            return self.out.put(packet, **kwargs)


def test_retained_hierarchy_and_shaper_release_only_the_selected_object():
    env = simpy.Environment()
    buffer = Port(
        env, 0, qlimit=400, limit_bytes=True, zero_downstream_buffer=True
    )
    aggregate = DRRServer(
        env, 800000, {"group": 1}, flow_classes=lambda p: "group",
        zero_buffer=True, zero_downstream_buffer=True,
    )
    priority = SPServer(
        env, 800, {0: 1, 1: 1, 2: 2},
        zero_buffer=True, zero_downstream_buffer=True,
    )
    shaper = TokenBucketShaper(env, 400, 200, zero_buffer=True)
    wire = Wire(env, lambda: .1)
    sink = Capture(env)
    departures = Capture(env, wire)
    buffer.out, aggregate.out, priority.out = aggregate, priority, shaper
    shaper.out, wire.out = departures, sink
    resident = PortMonitor(env, buffer, lambda: .25, True)
    upstream = ServerMonitor(env, aggregate, lambda: .25, True)
    downstream = ServerMonitor(env, priority, lambda: .25, True)

    first, low, high, last_high = [
        Packet(0, size, i, flow_id=flow)
        for i, (size, flow) in enumerate([(100, 0), (200, 1), (40, 2), (60, 2)])
    ]
    admitted = [first, low, high, last_high]
    releases = []
    update = buffer.update

    def release(packet):
        update(packet)
        releases.append((env.now, packet, list(buffer.store.items), buffer.byte_size))

    buffer.update = release
    for packet in admitted:
        buffer.put(packet)
    env.run(until=.3)

    # DRR's one aggregate FIFO takes .004 s in total. Its local monitor is
    # already empty, but all 400 bytes still consume shared admission capacity.
    assert resident.sizes == [4]
    assert resident.sizes_byte == [400]
    assert upstream.sizes["group"] == upstream.byte_sizes["group"] == [0]
    assert downstream.sizes == {0: [1], 1: [1], 2: [2]}
    assert downstream.byte_sizes == {0: [100], 1: [200], 2: [100]}
    rejected = Packet(env.now, 1, 4)
    assert buffer.put(rejected) is None
    assert buffer.packets_dropped == 1

    env.run(until=4.3)
    # SP finishes the last packet at 4.001. Its 200 bytes remain resident while
    # the shaper waits: only 150 of its 200 required byte tokens are available.
    assert priority.packet_in_service() is None
    assert all(samples[-1] == 0 for samples in downstream.byte_sizes.values())
    assert resident.sizes[-1] == 1
    assert resident.sizes_byte[-1] == 200
    assert buffer.store.items == [low]
    assert shaper.busy == 1
    env.run(until=5.3)

    expected = [first, high, last_high, low]
    # SP is nonpreemptive: the blocker takes 1 s, then high takes .4 + .6 s,
    # then low takes 2 s. Tokens accrue at 50 bytes/s; low needs one extra s.
    assert [packet for _, packet in departures.items] == expected
    assert [time for time, _ in departures.items] == pytest.approx(
        [1.001, 1.401, 2.001, 5.001]
    )
    assert [packet for _, packet in sink.items] == expected
    assert [time for time, _ in sink.items] == pytest.approx(
        [1.101, 1.501, 2.101, 5.101]
    )
    assert [packet for _, packet, *_ in releases] == expected
    assert [time for time, *_ in releases] == pytest.approx(
        [1.001, 1.401, 2.001, 5.001]
    )
    assert [remaining for _, _, remaining, _ in releases] == [
        [low, high, last_high], [low, last_high], [low], []
    ]
    assert [size for *_, size in releases] == [300, 260, 200, 0]
    assert sum(packet.size for _, packet in sink.items) == 400
    assert buffer.packets_received == 5
    assert buffer._packets_removed == 4
    assert buffer.byte_size == resident.sizes[-1] == resident.sizes_byte[-1] == 0
    assert not buffer.store.items and not buffer.downstream_store.items
    for scheduler in (aggregate, priority):
        assert not scheduler.upstream_stores and not scheduler.upstream_updates
        assert all(not store.items for store in scheduler.stores.values())
        assert all(not store.items for store in scheduler.downstream_stores.values())
        assert scheduler.packet_in_service() is None
        assert all(scheduler.size(cls) == 0 for cls in scheduler.all_flows())
        assert all(scheduler.byte_size(cls) == 0 for cls in scheduler.all_flows())
    assert shaper.packets_received == shaper.packets_sent == wire.packets_rec == 4
    assert not shaper.store.items and not shaper.upstream_stores
    assert not shaper.upstream_updates and not wire.store.items
    assert shaper.busy == 0


def test_reno_recovers_bottleneck_drops_after_token_wait_and_drains_short_tail():
    env = simpy.Environment()
    flow = Flow(7, "source", "receiver", size=1001, finish_time=.5)
    sender = TCPPacketGenerator(env, flow, TCPReno(mss=300, cwnd=1200))
    receiver = TCPSink(env)
    shaper = TokenBucketShaper(env, 1200, 1001)
    bottleneck = Port(env, 24000, qlimit=600, limit_bytes=True)
    data_wire, ack_wire = Wire(env, lambda: .01), Wire(env, lambda: .01)
    attempts, shaped = Capture(env, shaper), Capture(env, bottleneck)
    arrivals, acks = Capture(env, receiver), Capture(env, sender)
    sender.out, shaper.out, bottleneck.out = attempts, shaped, data_wire
    data_wire.out, receiver.out, ack_wire.out = arrivals, ack_wire, acks
    monitor = PortMonitor(env, bottleneck, lambda: .05, True)

    env.run(until=.3)
    # The full bucket passes 1001 bytes immediately. Resident capacity is only
    # 600 bytes, including service, so the third MSS and 101-byte tail drop.
    originals = [packet for _, packet in attempts.items]
    assert [(p.packet_id, p.size) for p in originals] == [
        (0, 300), (300, 300), (600, 300), (900, 101)
    ]
    assert [packet for _, packet in shaped.items] == originals
    assert [packet for _, packet in arrivals.items] == originals[:2]
    assert receiver.bytes_delivered == 600
    assert bottleneck.packets_dropped == 2
    assert monitor.sizes[0] == 2 and monitor.sizes_byte[0] == 600
    env.run(until=5)

    # The second ACK reaches the sender at .22, resetting its 1 s timer.
    # At 1.22 the shaper has 183 tokens; the 300-byte retry waits .78 s.
    # Its ACK at 2.12 starts the backed-off 2 s timer for the missing tail.
    assert [(p.packet_id, p.size) for _, p in attempts.items] == [
        (0, 300), (300, 300), (600, 300), (900, 101), (600, 300), (900, 101)
    ]
    assert [time for time, _ in attempts.items] == pytest.approx(
        [0, 0, 0, 0, 1.22, 4.12]
    )
    assert [time for time, _ in shaped.items] == pytest.approx(
        [0, 0, 0, 0, 2, 4.12]
    )
    assert [time for time, _ in arrivals.items] == pytest.approx(
        [.11, .21, 2.11, 4.12 + 101 * 8 / 24000 + .01]
    )
    assert [packet.ack for _, packet in acks.items] == [300, 600, 900, 1001]
    for original, (_, retry) in zip(originals[2:], attempts.items[4:]):
        assert retry is not original
        assert retry.time == original.time == 0
    assert [packet for _, packet in arrivals.items] == [
        originals[0], originals[1], attempts.items[4][1], attempts.items[5][1]
    ]

    sent_bytes = sum(packet.size for _, packet in attempts.items)
    dropped_bytes = sum(packet.size for packet in originals[2:])
    assert sent_bytes == 1402
    assert dropped_bytes == 401
    assert sent_bytes - dropped_bytes == receiver.bytes_received[7] == 1001
    assert receiver.bytes_delivered == sender.last_ack == sender.next_seq == 1001
    assert sender.bytes_in_flight == 0
    assert not sender.segment_state and not sender.sent_packets and not sender.timers
    assert sender.timer.stopped and not sender.action.is_alive
    assert bottleneck.packets_received == 6
    assert bottleneck._packets_removed == data_wire.packets_rec == 4
    assert bottleneck.byte_size == bottleneck.busy == bottleneck.busy_packet_size == 0
    assert monitor.sizes[-1] == monitor.sizes_byte[-1] == 0
    assert shaper.packets_received == shaper.packets_sent == 6
    assert shaper.busy == 0
    assert not shaper.store.items and not bottleneck.store.items
    assert not data_wire.store.items and not ack_wire.store.items
    # Observe past every old timer deadline: completion must remain quiescent.
    env.run(until=10)
    assert len(attempts.items) == 6
    assert monitor.sizes[-1] == monitor.sizes_byte[-1] == 0
