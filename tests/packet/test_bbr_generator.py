import pytest

from ns.flow.flow import AppType, Flow
from ns.packet.bbr_generator import BBRPacketGenerator
from ns.packet.packet import Packet

simpy = pytest.importorskip("simpy")


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

    def restart(self, revised_rto, start_time=0):
        self.rto = revised_rto
        self.restart_calls.append((revised_rto, start_time))


class DummyCC:
    def __init__(self, cwnd=4096):
        self.cwnd = cwnd
        self.pacing_rate = 0
        self.next_departure_time = 0
        self.calls = []

    def timer_expired(self, packet=None):
        self.calls.append(("timer_expired", packet))

    def dupack_over(self):
        self.calls.append(("dupack_over",))

    def consecutive_dupacks_received(self, packet=None):
        self.calls.append(("consecutive_dupacks_received", packet))

    def more_dupacks_received(self, packet=None):
        self.calls.append(("more_dupacks_received", packet))

    def set_before_control(self, current_time, packet_in_flight):
        self.calls.append(("set_before_control", current_time, packet_in_flight))

    def ack_received(self, rtt, current_time):
        self.calls.append(("ack_received", rtt, current_time))


def make_flow(size, finish_time=1.0):
    return Flow(
        fid=1,
        src="src",
        dst="dst",
        size=size,
        finish_time=finish_time,
        typ=AppType.BULK_TRANSFER,
    )


def make_sender(env, size, cwnd=4096, finish_time=1.0):
    sender = BBRPacketGenerator(
        env,
        make_flow(size, finish_time),
        DummyCC(cwnd),
        debug=False,
    )
    sink = CaptureSink(env)
    sender.out = sink
    return sender, sink


def make_ack(
    packet_id,
    *,
    ack,
    time,
    delivered_time,
    first_sent_time,
    delivered=0,
    lost=0,
    is_app_limited=False,
    flow_id=10001,
):
    ack_packet = Packet(
        time=time,
        size=40,
        packet_id=packet_id,
        flow_id=flow_id,
        src="dst",
        dst="src",
    )
    ack_packet.ack = ack
    ack_packet.delivered_time = delivered_time
    ack_packet.first_sent_time = first_sent_time
    ack_packet.delivered = delivered
    ack_packet.lost = lost
    ack_packet.is_app_limited = is_app_limited
    return ack_packet


def test_bbr_sender_sends_buffered_sub_mss_data():
    env = simpy.Environment()
    sender, sink = make_sender(env, size=300)

    env.run(until=0.01)

    assert [packet.size for packet in sink.packets] == [300]


def test_bbr_sender_sends_final_tail_segment():
    env = simpy.Environment()
    sender, sink = make_sender(env, size=768)

    env.run(until=0.01)

    assert [packet.size for packet in sink.packets] == [512, 256]


def test_bbr_sender_fast_retransmit_emits_fresh_packet_without_resetting_timestamp():
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
    original.delivered_time = 1.0
    original.first_sent_time = 0.0
    original.delivered = 0
    original.self_lost = False
    sender.sent_packets[0] = original
    sender.max_ack = 0
    sender.next_seq = 512
    sender.packet_in_flight = 512
    sender.dupack = 1
    sender.timer = DummyTimer(rto=1.0)

    sender.put(
        make_ack(
            0,
            ack=0,
            time=1.0,
            delivered_time=1.0,
            first_sent_time=0.0,
        )
    )

    assert any(
        call[0] == "consecutive_dupacks_received"
        for call in sender.congestion_control.calls
    )
    assert sink.packets[0] is not original
    assert sink.waits[0] == pytest.approx(4.0)
    assert original.time == 1.0


def test_bbr_sender_timeout_retransmit_emits_fresh_packet_without_resetting_timestamp():
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
    original.delivered_time = 1.0
    original.first_sent_time = 0.0
    original.delivered = 0
    original.self_lost = False
    sender.sent_packets[0] = original
    sender.max_ack = 0
    sender.next_seq = 512
    sender.packet_in_flight = 512
    sender.timer = DummyTimer(rto=1.0)

    sender.timeout_callback(0)

    assert sender.congestion_control.calls[0][0] == "set_before_control"
    assert sender.congestion_control.calls[1][0] == "timer_expired"
    assert sink.packets[0] is not original
    assert sink.waits[0] == pytest.approx(4.0)
    assert original.time == 1.0


def test_bbr_sender_keeps_timeout_pointer_on_oldest_outstanding_segment():
    env = simpy.Environment()
    sender, sink = make_sender(env, size=1024)

    env.run(until=0.01)

    sender.timer = DummyTimer(rto=sender.rto)

    assert sender.to_pkt_id == 0

    sender.timeout_callback(0)

    assert sink.packets[-1].packet_id == 0
    assert sender.to_pkt_id == 0


def test_bbr_sender_cleans_up_short_segments_with_segment_end_ack():
    env = simpy.Environment(initial_time=5)
    sender, _ = make_sender(env, size=1024)
    first = Packet(
        time=0.0,
        size=256,
        packet_id=0,
        flow_id=1,
        src="src",
        dst="dst",
    )
    second = Packet(
        time=0.0,
        size=256,
        packet_id=256,
        flow_id=1,
        src="src",
        dst="dst",
    )
    for packet in (first, second):
        packet.delivered_time = 1.0
        packet.first_sent_time = 0.0
        packet.delivered = packet.packet_id
        packet.self_lost = False

    sender.sent_packets = {0: first, 256: second}
    sender.max_ack = 0
    sender.last_ack = 0
    sender.next_seq = 512
    sender.packet_in_flight = 512

    sender.put(
        make_ack(
            0,
            ack=512,
            time=0.0,
            delivered_time=1.0,
            first_sent_time=0.0,
        )
    )

    assert sender.sent_packets == {}
    assert sender.packet_in_flight == 0
    assert sender.max_ack == 512


def test_bbr_sender_rate_sample_stays_stable_across_retransmit_timing_changes():
    def run_scenario(include_timeout):
        env = simpy.Environment(initial_time=5)
        sender, _ = make_sender(env, size=1024)
        original = Packet(
            time=0.0,
            size=512,
            packet_id=0,
            flow_id=1,
            src="src",
            dst="dst",
        )
        original.delivered_time = 1.0
        original.first_sent_time = 0.0
        original.delivered = 0
        original.self_lost = False
        sender.sent_packets[0] = original
        sender.max_ack = 0
        sender.last_ack = 0
        sender.next_seq = 512
        sender.packet_in_flight = 512
        sender.timer = DummyTimer(rto=1.0)

        if include_timeout:
            sender.timeout_callback(0)

        sender.put(
            make_ack(
                0,
                ack=512,
                # ACKs keep the segment's original transmit timestamp even
                # after a retransmission attempt.
                time=0.0,
                delivered_time=1.0,
                first_sent_time=0.0,
            )
        )
        ack_calls = [
            call for call in sender.congestion_control.calls if call[0] == "ack_received"
        ]
        return (
            ack_calls[-1][1:],
            sender.congestion_control.rs.send_elapsed,
            sender.congestion_control.rs.ack_elapsed,
            sender.congestion_control.rs.delivery_rate,
        )

    clean = run_scenario(include_timeout=False)
    retransmitted = run_scenario(include_timeout=True)

    assert retransmitted == clean


def test_bbr_sender_samples_rtt_from_the_acked_packet_time():
    env = simpy.Environment(initial_time=8)
    sender, _ = make_sender(env, size=1024)
    first = Packet(
        time=1.0,
        size=512,
        packet_id=0,
        flow_id=1,
        src="src",
        dst="dst",
    )
    second = Packet(
        time=3.0,
        size=512,
        packet_id=512,
        flow_id=1,
        src="src",
        dst="dst",
    )
    for packet in (first, second):
        packet.delivered_time = 1.0
        packet.delivered = packet.packet_id
        packet.first_sent_time = 1.0
        packet.self_lost = False

    sender.sent_packets = {0: first, 512: second}
    sender.max_ack = 0
    sender.last_ack = 0
    sender.next_seq = 1024
    sender.packet_in_flight = 1024
    sender.timer = DummyTimer(rto=1.0)

    sender.put(
        make_ack(
            512,
            ack=1024,
            time=3.0,
            delivered_time=1.0,
            first_sent_time=1.0,
        )
    )

    assert sender.congestion_control.calls[-1] == ("ack_received", 5.0, 8)
    assert sender.rtt_estimate == pytest.approx(5.0)
    assert sender.rto == pytest.approx(15.0)
