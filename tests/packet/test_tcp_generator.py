import pytest

simpy = pytest.importorskip("simpy")

from ns.flow.cc import TCPReno
from ns.flow.flow import Flow
from ns.packet.packet import Packet
from ns.packet.tcp_generator import TCPPacketGenerator
from ns.packet.tcp_sink import TCPSink


class CaptureSink:
    def __init__(self, env):
        self.env = env
        self.packets = []
        self.waits = []

    def put(self, packet):
        self.packets.append(packet)
        self.waits.append(self.env.now - packet.time)


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


def make_sender(env, size, cwnd=4096, finish_time=10):
    flow = Flow(fid=1, src="src", dst="dst", size=size, finish_time=finish_time)
    sender = TCPPacketGenerator(env, flow, DummyCC(cwnd))
    sink = CaptureSink(env)
    sender.out = sink
    return sender, sink


def make_ack(seq, *, time=0.0, flow_id=10001):
    packet = Packet(time, 40, seq, flow_id=flow_id, src="dst", dst="src")
    packet.ack = seq
    return packet


def test_tcp_sender_sends_buffered_sub_mss_data():
    env = simpy.Environment()
    _, sink = make_sender(env, size=300)
    env.run(until=0.01)
    assert [packet.size for packet in sink.packets] == [300]


def test_tcp_sender_sends_final_tail_segment():
    env = simpy.Environment()
    _, sink = make_sender(env, size=768)
    env.run(until=0.01)
    assert [packet.size for packet in sink.packets] == [512, 256]


def test_tcp_sender_fast_retransmit_emits_fresh_packet_without_resetting_timestamp():
    env = simpy.Environment(initial_time=1.5)
    sender, sink = make_sender(env, size=1024)
    env.run(until=2)
    original = sink.packets[0]
    for _ in range(3):
        sender.put(make_ack(0, time=1.5))
    retransmission = sink.packets[-1]
    assert sender.congestion_control.consecutive_dupacks_calls == 1
    assert retransmission is not original
    assert (retransmission.packet_id, retransmission.size) == (0, 512)
    assert sink.waits[-1] == pytest.approx(0.5)
    assert retransmission.time == original.time == 1.5


def test_tcp_sender_timeout_retransmit_emits_fresh_packet_without_resetting_timestamp():
    env = simpy.Environment(initial_time=1.25)
    sender, sink = make_sender(env, size=512)
    env.run(until=1.3)
    original = sink.packets[0]
    env.run(until=2.26)
    retransmission = sink.packets[-1]
    assert sender.congestion_control.timer_expired_calls == 1
    assert retransmission is not original
    assert sink.waits[-1] == pytest.approx(1)
    assert retransmission.time == original.time == 1.25


def test_tcp_sender_keeps_unacknowledged_suffix_of_partially_acked_segment():
    env = simpy.Environment(initial_time=5)
    sender, sink = make_sender(env, size=256)
    env.run(until=5.1)
    original = sink.packets[0]
    sender.put(make_ack(128))
    # ACKed prefix bytes retire, but the original packet stays unchanged and the
    # remaining suffix still has a timer. The previous test fabricated unsent
    # packets and required a timer for the already ACKed start sequence.
    assert set(sender.segment_state) == set(sender.timers) == {128}
    assert sender.segment_state[128].size == 128
    assert sender.bytes_in_flight == 128
    assert not sender.timer.stopped
    assert (original.packet_id, original.size) == (0, 256)
    env.run(until=6.11)
    assert (sink.packets[-1].packet_id, sink.packets[-1].size) == (128, 128)
    sender.put(make_ack(256))
    assert sender.segment_state == {}


def test_tcp_sender_skips_rtt_update_for_ack_covering_retransmitted_data():
    env = simpy.Environment()
    sender, sink = make_sender(env, size=1024)
    env.run(until=0.2)
    sender.put(make_ack(512))
    assert sender.smoothed_rtt == pytest.approx(0.2)
    env.run(until=1.21)
    assert sink.packets[-1].packet_id == 512
    assert sender.congestion_control.timer_expired_calls == 1
    before = (sender.smoothed_rtt, sender.rtt_var, sender.rto)
    sender.congestion_control.ack_received_calls.clear()
    sender.put(make_ack(1024, time=1.2))
    assert sender.congestion_control.ack_received_calls == [(0.2, 1.21)]
    assert (sender.smoothed_rtt, sender.rtt_var, sender.rto) == before
    assert sender.segment_state == {}


def test_tcp_sender_ignores_dupacks_after_completion():
    env = simpy.Environment()
    sender, sink = make_sender(env, size=1024)
    env.run(until=0.2)
    sender.put(make_ack(1024))
    for _ in range(4):
        sender.put(make_ack(1024))
    # There are no outstanding bytes, so duplicate ACKs cannot signal loss. The
    # previous fixture asserted a controller loss notification for nonexistent
    # segments despite its test name claiming that these ACKs were ignored.
    assert sender.congestion_control.consecutive_dupacks_calls == 0
    assert len(sink.packets) == 2
    assert sender.dupack == 0
    assert sender.timers == {}


def test_reno_short_final_ack_grows_only_by_delivered_bytes():
    env = simpy.Environment()
    cc = TCPReno(mss=300, cwnd=300)
    sender = TCPPacketGenerator(env, Flow(1, "src", "dst", size=701), cc)
    receiver = TCPSink(env)
    sender.out = receiver
    receiver.out = sender
    env.run(until=0.1)
    # The synchronous receiver ACKs 300, 300, and 101 bytes: all are
    # slow-start credit, including the exact tail rather than a third MSS.
    assert cc.cwnd == 1001
    assert sender.last_ack == receiver.bytes_delivered == 701
    assert sender.bytes_in_flight == 0
    assert sender.segment_state == {}
    assert sender.timer is not None
    assert sender.timer.stopped


def test_reno_cumulative_ack_bridge_carries_bytes_and_no_fabricated_rtt():
    class RecordingReno(TCPReno):
        def ack_received_bytes(self, acknowledged_bytes, rtt, current_time):
            observations.append((acknowledged_bytes, rtt, self.flight_size))
            super().ack_received_bytes(acknowledged_bytes, rtt, current_time)

    observations = []
    env = simpy.Environment()
    cc = RecordingReno(mss=1000, cwnd=3000, ssthresh=3000)
    sender = TCPPacketGenerator(env, Flow(1, "src", "dst", size=3000), cc)
    captured = CaptureSink(env)
    receiver = TCPSink(env)
    sender.out = captured
    receiver.out = sender
    env.run(until=0.1)
    # Two out-of-order segments produce two duplicate ACKs; filling the gap
    # then ACKs three segments together, so Karn supplies no fresh RTT sample.
    for index in (1, 2, 0):
        receiver.put(captured.packets[index])
    assert observations == [(3000, None, 3000)]
    assert cc.cwnd == 4000
    assert sender.last_ack == receiver.bytes_delivered == 3000
    assert sender.segment_state == {}
    assert sender.timer is not None
    assert sender.timer.stopped


def test_reno_ack_bridge_preserves_measured_zero_rtt():
    class RecordingReno(TCPReno):
        def ack_received_bytes(self, acknowledged_bytes, rtt, current_time):
            observations.append((acknowledged_bytes, rtt))
            super().ack_received_bytes(acknowledged_bytes, rtt, current_time)

    observations = []
    env = simpy.Environment()
    cc = RecordingReno(mss=300, cwnd=300)
    sender = TCPPacketGenerator(env, Flow(1, "src", "dst", size=123), cc)
    receiver = TCPSink(env)
    sender.out = receiver
    receiver.out = sender
    env.run(until=0.1)
    assert observations == [(123, 0)]
    assert sender._rtt_initialized


@pytest.mark.parametrize("loss", ["timeout", "duplicate_acks"])
def test_reno_transport_loss_halves_flight_instead_of_larger_window(loss):
    env = simpy.Environment()
    cc = TCPReno(mss=1000, cwnd=30000)
    sender = TCPPacketGenerator(env, Flow(1, "src", "dst", size=10000), cc)
    captured = CaptureSink(env)
    sender.out = captured
    env.run(until=0.1)
    assert sender.bytes_in_flight == 10000
    if loss == "timeout":
        env.run(until=1.01)
    else:
        for _ in range(3):
            sender.put(make_ack(0))
    assert cc.ssthresh == 5000
    assert cc.cwnd == (1000 if loss == "timeout" else 8000)
    assert captured.packets[-1].packet_id == 0
    assert len(captured.packets) == 11


def test_reno_recovery_ack_transitions_have_no_extra_window_growth():
    env = simpy.Environment()
    cc = TCPReno(mss=1000, cwnd=30000)
    sender = TCPPacketGenerator(env, Flow(1, "src", "dst", size=10000), cc)
    captured = CaptureSink(env)
    sender.out = captured
    env.run(until=0.1)
    for _ in range(4):
        sender.put(make_ack(0))
    assert cc.cwnd == 9000
    sender.put(make_ack(2000))
    assert cc.cwnd == 6000  # partial ACK: threshold plus one replacement segment
    env.run(until=0.11)
    assert captured.packets[-1].packet_id == 2000
    sender.put(make_ack(10000))
    assert cc.cwnd == 5000  # exit ACK deflates without ordinary ACK growth
    assert sender.last_ack == 10000
    assert sender.segment_state == {}
    assert sender.timer is not None
    assert sender.timer.stopped


def test_first_two_duplicate_acks_do_not_leave_unused_controller_context():
    env = simpy.Environment()
    cc = TCPReno(mss=1000, cwnd=30000)
    sender = TCPPacketGenerator(env, Flow(1, "src", "dst", size=10000), cc)
    sender.out = CaptureSink(env)
    env.run(until=0.1)
    for _ in range(2):
        sender.put(make_ack(0))
    # These ACKs do not call a control action. A later direct controller call
    # must therefore use its documented window fallback, not unused flight.
    cc.timer_expired()
    assert cc.ssthresh == 15000
