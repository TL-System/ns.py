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


class DummyCC:
    def __init__(self, cwnd=4096, mss=512):
        self.cwnd = cwnd
        self.mss = mss
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


def make_sender(env, size, *, mss=512, rtt=3, pacing=0):
    flow = Flow(1, "src", "dst", size=size, typ=AppType.BULK_TRANSFER)
    cc = DummyCC(mss=mss)
    cc.pacing_rate = pacing
    sender = BBRPacketGenerator(env, flow, cc, rtt_estimate=rtt, debug=False)
    sink = CaptureSink(env)
    sender.out = sink
    return sender, sink


def make_ack(frontier, time=0):
    packet = Packet(time, 40, 0, flow_id=10001)
    packet.ack = frontier
    return packet


def test_bbr_sender_sends_buffered_sub_mss_data():
    env = simpy.Environment()
    sender, sink = make_sender(env, 300)
    env.run(until=0.01)
    assert [packet.size for packet in sink.packets] == [300]


def test_bbr_sender_sends_final_tail_segment():
    env = simpy.Environment()
    sender, sink = make_sender(env, 768)
    env.run(until=0.01)
    assert [packet.size for packet in sink.packets] == [512, 256]


def test_bbr_sender_fast_retransmit_is_fresh_and_preserves_original_latency():
    env = simpy.Environment(initial_time=1)
    sender, sink = make_sender(env, 1024)
    env.run(until=5)
    original = sink.packets[0]
    original.perhop_time["queue"] = 1.1
    for _ in range(3):
        sender.put(make_ack(0))
    retransmitted = sink.packets[-1]
    assert any(c[0] == "consecutive_dupacks_received"
               for c in sender.congestion_control.calls)
    assert retransmitted is not original
    assert retransmitted.perhop_time == {}
    assert sink.waits[-1] == pytest.approx(4)
    assert original.time == 1
    assert original.perhop_time == {"queue": 1.1}
    assert sender.segment_state[0].last_tx_time == 5


def test_bbr_sender_timeout_is_fresh_and_preserves_original_latency():
    env = simpy.Environment(initial_time=1)
    sender, sink = make_sender(env, 1024)
    env.run(until=5)
    original = sink.packets[0]
    sender.timeout_callback()
    assert sender.congestion_control.calls[0][0] == "set_before_control"
    assert sender.congestion_control.calls[1][0] == "timer_expired"
    assert sink.packets[-1] is not original
    assert sink.waits[-1] == pytest.approx(4)
    assert original.time == 1
    assert sender.rto == 12


def test_bbr_sender_keeps_timeout_pointer_on_oldest_outstanding_segment():
    env = simpy.Environment()
    sender, sink = make_sender(env, 1024)
    env.run(until=0.01)
    assert sender.to_pkt_id == 0
    sender.timeout_callback()
    assert sink.packets[-1].packet_id == sender.to_pkt_id == 0
    sender.put(make_ack(512))
    assert sender.to_pkt_id == 512
    sender.timeout_callback()
    assert sink.packets[-1].packet_id == 512


def test_bbr_sender_cleans_up_short_segments_with_segment_end_ack():
    env = simpy.Environment()
    sender, _ = make_sender(env, 512, mss=256)
    env.run(until=5)
    sender.put(make_ack(512))
    assert sender.sent_packets == sender.segment_state == {}
    assert sender.packet_in_flight == 0
    assert sender.max_ack == 512
    assert sender.timer is None


def test_bbr_sender_keeps_rate_timestamps_but_rejects_retransmitted_rtt():
    def run_scenario(include_timeout):
        env = simpy.Environment(initial_time=1)
        sender, sink = make_sender(env, 512)
        env.run(until=5)
        original = sink.packets[0]
        if include_timeout:
            sender.timeout_callback()
        sender.put(make_ack(512, time=1))
        calls = [c for c in sender.congestion_control.calls if c[0] == "ack_received"]
        assert original.delivered_time == 1
        return (calls[-1][1:], sender.congestion_control.rs.send_elapsed,
                sender.congestion_control.rs.ack_elapsed,
                sender.congestion_control.C.delivered)

    clean = run_scenario(False)
    retransmitted = run_scenario(True)
    assert retransmitted[1:] == clean[1:] == (0, 4, 512)
    assert clean[0] == (4, 5)
    assert retransmitted[0] == (0, 5)


def test_bbr_sender_rejects_rtt_from_ambiguous_cumulative_ack():
    env = simpy.Environment(initial_time=1)
    sender, sink = make_sender(env, 1024, rtt=7, pacing=256)
    env.run(until=8)
    assert [packet.time for packet in sink.packets] == [1, 3]
    sender.put(make_ack(1024, time=3))
    assert sender.congestion_control.calls[-1] == ("ack_received", 0, 8)
    assert sender.rtt_estimate == 7
    assert sender.rto == 14
