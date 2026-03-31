import pytest

from ns.flow.flow import Flow
from ns.packet.packet import Packet
from ns.packet.tcp_generator import TCPPacketGenerator

simpy = pytest.importorskip("simpy")


class CaptureSink:
    def __init__(self):
        self.packets = []

    def put(self, packet):
        self.packets.append(packet)


class DummyTimer:
    def __init__(self, rto):
        self.rto = rto
        self.restart_calls = []
        self.stop_calls = 0

    def restart(self, revised_rto, start_time=0):
        self.rto = revised_rto
        self.restart_calls.append((revised_rto, start_time))

    def stop(self):
        self.stop_calls += 1


class DummyCC:
    def __init__(self, cwnd=4096):
        self.cwnd = cwnd
        self.calls = []

    def ack_received(self, rtt=0, current_time=0):
        self.calls.append(("ack_received", rtt, current_time))

    def timer_expired(self):
        self.calls.append(("timer_expired",))

    def dupack_over(self):
        self.calls.append(("dupack_over",))

    def consecutive_dupacks_received(self):
        self.calls.append(("consecutive_dupacks_received",))

    def more_dupacks_received(self):
        self.calls.append(("more_dupacks_received",))


def make_flow(size, finish_time=1.0):
    return Flow(
        fid=1,
        src="src",
        dst="dst",
        size=size,
        finish_time=finish_time,
    )


def make_sender(env, size, cwnd=4096, finish_time=1.0):
    sender = TCPPacketGenerator(env, make_flow(size, finish_time), DummyCC(cwnd))
    sender.out = CaptureSink()
    return sender


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
    sender = make_sender(env, size=300)

    env.run(until=0.01)

    assert [packet.size for packet in sender.out.packets] == [300]


def test_tcp_sender_sends_final_tail_segment():
    env = simpy.Environment()
    sender = make_sender(env, size=768)

    env.run(until=0.01)

    assert [packet.size for packet in sender.out.packets] == [512, 256]


def test_tcp_sender_fast_retransmit_emits_fresh_packet_without_resetting_timestamp():
    env = simpy.Environment()
    sender = make_sender(env, size=1024)
    original = Packet(
        time=7.0,
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

    sender.put(make_ack(0, time=7.0))

    assert sender.out.packets[0] is not original
    assert sender.out.packets[0].time == 7.0
    assert original.time == 7.0


def test_tcp_sender_timeout_retransmit_emits_fresh_packet_without_resetting_timestamp():
    env = simpy.Environment()
    sender = make_sender(env, size=1024)
    original = Packet(
        time=3.0,
        size=512,
        packet_id=0,
        flow_id=1,
        src="src",
        dst="dst",
    )
    sender.sent_packets[0] = original
    sender.timers[0] = DummyTimer(rto=1.0)

    sender.timeout_callback(0)

    assert sender.out.packets[0] is not original
    assert sender.out.packets[0].time == 3.0
    assert original.time == 3.0


def test_tcp_sender_keeps_partially_acknowledged_segment_until_segment_end():
    env = simpy.Environment()
    sender = make_sender(env, size=1024)
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


def test_tcp_sender_skips_rtt_update_for_ack_covering_retransmitted_data():
    env = simpy.Environment()
    sender = make_sender(env, size=1024)
    original = Packet(
        time=0.0,
        size=512,
        packet_id=0,
        flow_id=1,
        src="src",
        dst="dst",
    )
    sender.sent_packets[0] = original
    sender.timers[0] = DummyTimer(rto=1.0)
    sender.smoothed_rtt = 1.0
    sender.rtt_var = 0.25
    sender.rto = 2.0

    sender.timeout_callback(0)
    before = (sender.smoothed_rtt, sender.rtt_var, sender.rto)

    sender.put(make_ack(512, time=-1.0))

    after = (sender.smoothed_rtt, sender.rtt_var, sender.rto)
    assert after == before
