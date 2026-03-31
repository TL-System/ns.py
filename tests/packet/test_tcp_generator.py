import pytest

simpy = pytest.importorskip("simpy")

from ns.flow.flow import Flow
from ns.packet.packet import Packet
from ns.packet.tcp_generator import TCPPacketGenerator


class CaptureSink:
    def __init__(self, env):
        self.env = env
        self.packets = []
        self.waits = []

    def put(self, packet):
        self.packets.append(packet)
        self.waits.append(self.env.now - packet.time)


class DummyTimer:
    def __init__(self, rto=1.0):
        self.rto = rto
        self.restart_calls = []
        self.stop_calls = 0

    def stop(self):
        self.stop_calls += 1

    def restart(self, revised_rto):
        self.rto = revised_rto
        self.restart_calls.append(revised_rto)


class DummyCC:
    def __init__(self, cwnd=4096):
        self.cwnd = cwnd
        self.consecutive_dupacks_calls = 0
        self.more_dupacks_calls = 0
        self.dupack_over_calls = 0
        self.timer_expired_calls = 0
        self.ack_received_calls = []

    def timer_expired(self):
        self.timer_expired_calls += 1

    def dupack_over(self):
        self.dupack_over_calls += 1

    def consecutive_dupacks_received(self):
        self.consecutive_dupacks_calls += 1

    def more_dupacks_received(self):
        self.more_dupacks_calls += 1

    def ack_received(self, sample_rtt, current_time):
        self.ack_received_calls.append((sample_rtt, current_time))


def make_flow(size, finish_time=1.0):
    return Flow(fid=1, src="src", dst="dst", size=size, finish_time=finish_time)


def make_sender(env, size, cwnd=4096, finish_time=1.0):
    sender = TCPPacketGenerator(env, make_flow(size, finish_time), DummyCC(cwnd))
    sink = CaptureSink(env)
    sender.out = sink
    return sender, sink


def make_ack(seq, *, time=0.0, flow_id=10001):
    ack = Packet(
        time=time,
        size=40,
        packet_id=seq,
        flow_id=flow_id,
        src="dst",
        dst="src",
    )
    ack.ack = seq
    return ack


def test_tcp_sender_sends_buffered_sub_mss_data():
    env = simpy.Environment()
    sender, sink = make_sender(env, size=300)

    env.run(until=0.01)

    assert [packet.size for packet in sink.packets] == [300]


def test_tcp_sender_sends_final_tail_segment():
    env = simpy.Environment()
    sender, sink = make_sender(env, size=768)

    env.run(until=0.01)

    assert [packet.size for packet in sink.packets] == [512, 256]


def test_tcp_sender_fast_retransmit_emits_fresh_packet_without_resetting_timestamp():
    env = simpy.Environment(initial_time=5)
    sender, sink = make_sender(env, size=1024)
    original = Packet(
        time=1.5,
        size=512,
        packet_id=0,
        flow_id=1,
        src="src",
        dst="dst",
    )
    sender.sent_packets[0] = original
    sender.last_ack = 0
    sender.dupack = 2
    sender.next_seq = 512

    sender.put(make_ack(0, time=1.5))

    assert sender.congestion_control.consecutive_dupacks_calls == 1
    assert sink.packets[0] is not original
    assert sink.waits[0] == pytest.approx(3.5)
    assert original.time == 1.5


def test_tcp_sender_timeout_retransmit_emits_fresh_packet_without_resetting_timestamp():
    env = simpy.Environment(initial_time=5)
    sender, sink = make_sender(env, size=1024)
    original = Packet(
        time=1.25,
        size=512,
        packet_id=0,
        flow_id=1,
        src="src",
        dst="dst",
    )
    sender.sent_packets[0] = original
    sender.timers[0] = DummyTimer(rto=1.0)

    sender.timeout_callback(0)

    assert sender.congestion_control.timer_expired_calls == 1
    assert sink.packets[0] is not original
    assert sink.waits[0] == pytest.approx(3.75)
    assert original.time == 1.25


def test_tcp_sender_keeps_partially_acknowledged_segment_until_segment_end():
    env = simpy.Environment(initial_time=5)
    sender, _ = make_sender(env, size=1024)
    partial = Packet(
        time=0.0,
        size=256,
        packet_id=0,
        flow_id=1,
        src="src",
        dst="dst",
    )
    sender.sent_packets[0] = partial
    sender.timers[0] = DummyTimer(rto=1.0)

    sender.put(make_ack(128, time=0.0))

    assert 0 in sender.sent_packets
    assert 0 in sender.timers
    assert sender.timers[0].stop_calls == 0


def test_tcp_sender_skips_rtt_update_for_ack_covering_retransmitted_data():
    env = simpy.Environment(initial_time=5)
    sender, sink = make_sender(env, size=1024)
    original = Packet(
        time=1.0,
        size=512,
        packet_id=0,
        flow_id=1,
        src="src",
        dst="dst",
    )
    sender.sent_packets[0] = original
    sender.timers[0] = DummyTimer(rto=1.0)
    sender.last_ack = 0
    sender.dupack = 2
    sender.next_seq = 512
    sender.smoothed_rtt = 1.0
    sender.rtt_var = 0.25
    sender.rto = 2.0
    sender.last_rtt_sample = 1.0

    sender.put(make_ack(0, time=1.0))
    sender.put(make_ack(0, time=1.0))
    sender.put(make_ack(0, time=1.0))
    sink.packets.clear()
    sink.waits.clear()
    sender.congestion_control.ack_received_calls.clear()
    before = (sender.smoothed_rtt, sender.rtt_var, sender.rto)

    sender.put(make_ack(512, time=1.2))

    assert sender.congestion_control.ack_received_calls == [(1.0, 5)]
    assert (sender.smoothed_rtt, sender.rtt_var, sender.rto) == before
    assert sink.packets == []


def test_tcp_sender_ignores_dupacks_for_unknown_segment_frontier():
    env = simpy.Environment(initial_time=5)
    sender, sink = make_sender(env, size=1024)
    sender.last_ack = 1024
    sender.dupack = 2
    sender.next_seq = 1536

    sender.put(make_ack(1024, time=1.0))

    assert sender.congestion_control.consecutive_dupacks_calls == 1
    assert sink.packets == []
