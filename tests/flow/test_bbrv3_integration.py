"""Observe real pacing, a bottleneck, idle application writes, and recovery."""

import pytest
import simpy

from ns.flow.bbr import BBR, BBRState
from ns.flow.flow import AppType, Flow
from ns.packet.bbr_generator import BBRPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.port.port import Port
from ns.port.wire import Wire


def connect(env, flow, cc, *, bottleneck=None, lose_first=False):
    sender = BBRPacketGenerator(env, flow, cc, debug=False)
    receiver = TCPSink(env, debug=False)
    down, up = Wire(env, lambda: 0.005), Wire(env, lambda: 0.005)
    records = []

    class DataPath:
        def put(self, packet):
            records.append((env.now, packet))
            if not (lose_first and len(records) == 1):
                down.put(packet)

    sender.out = DataPath()
    if bottleneck:
        port = Port(env, rate=8 * bottleneck)  # Link expects bits/s, BBR bytes/s.
        down.out, port.out = port, receiver
    else:
        down.out = receiver
    receiver.out, up.out = up, sender
    return sender, receiver, records


def test_bbr_end_to_end_reaches_probe_bw_at_known_bottleneck():
    env = simpy.Environment()
    flow = Flow(42, "src", "dst", size=512 * 800, finish_time=5)
    cc = BBR(mss=512, cwnd=8192, rtt_estimate=0.02)
    sender, receiver, records = connect(env, flow, cc, bottleneck=100_000)
    env.run(until=15)
    assert receiver.bytes_delivered == flow.size
    assert cc.C is not None and cc.rs is not None
    assert cc.C.delivered == flow.size
    assert cc.state == BBRState.PROBE_BW
    assert cc.filled_pipe
    assert cc.max_bw == pytest.approx(100_000)
    assert sender.packet_in_flight == 0
    assert sender.timer is None
    # Before the first feedback, the initial cwnd/RTT and Startup gain determine
    # spacing. This checks physical sends, independently of later rate samples.
    assert records[0][0] == 0
    assert records[1][0] == pytest.approx(512 / (2.885 * 8192 / 0.02))


def test_sparse_application_writes_preserve_delivery_without_false_full_pipe():
    env = simpy.Environment()
    flow = Flow(42, "src", "dst", size=500, finish_time=2,
                typ=AppType.VIDEO, arrival_dist=lambda: 0.2,
                size_dist=lambda: 100)
    cc = BBR(mss=100, cwnd=800, rtt_estimate=0.02)
    sender, receiver, records = connect(env, flow, cc)
    env.run(until=5)
    assert [time for time, _ in records] == pytest.approx([0.2, 0.4, 0.6, 0.8, 1])
    assert all(packet.is_app_limited for _, packet in records)
    assert cc.C is not None and cc.rs is not None
    assert cc.C.delivered == receiver.bytes_delivered == 500
    assert cc.max_bw == pytest.approx(10_000)  # 100 bytes / 10 ms RTT.
    assert not cc.filled_pipe
    assert sender.timer is None


def test_bbr_fast_loss_counts_unique_bytes_and_uses_attempt_clock():
    env = simpy.Environment()
    flow = Flow(42, "src", "dst", size=700, finish_time=1)
    cc = BBR(mss=100, cwnd=400, rtt_estimate=0.02)
    sender, receiver, records = connect(env, flow, cc, lose_first=True)
    env.run(until=5)
    zero_attempts = [(time, packet) for time, packet in records if packet.packet_id == 0]
    assert len(zero_attempts) == 2
    assert zero_attempts[1][0] < 1  # Fast retransmit, before the one-second RTO.
    assert all(packet.time == 0 for _, packet in zero_attempts)
    assert zero_attempts[1][1].sent_time == zero_attempts[1][0]
    assert cc.C is not None and cc.rs is not None
    assert receiver.bytes_delivered == cc.C.delivered == 700
    assert cc.C is not None and cc.rs is not None
    assert cc.C.lost == 100
    assert not cc.packet_conservation
    assert sender.packet_in_flight == 0
    assert sender.timer is None
    assert cc.min_rtt >= 0.01 - 1e-12  # Ambiguous recovery ACKs never teach zero.


def test_synchronous_ack_has_delivery_credit_but_no_rate():
    env = simpy.Environment()
    cc = BBR(mss=100, cwnd=400)
    flow = Flow(42, "src", "dst", size=700)
    sender = BBRPacketGenerator(env, flow, cc, debug=False)
    receiver = TCPSink(env, debug=False)
    sender.out, receiver.out = receiver, sender
    env.run(until=5)
    assert cc.C is not None and cc.rs is not None
    assert receiver.bytes_delivered == cc.C.delivered == 700
    assert cc.C is not None and cc.rs is not None
    assert cc.max_bw == cc.rs.delivery_rate == 0
    assert cc.min_rtt == 0
    assert sender.timer is None
