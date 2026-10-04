"""Transport checks use a passive controller to isolate BBR sender mechanics."""

import pytest
import simpy

from ns.flow.flow import AppType, Flow
from ns.packet.bbr_generator import BBRPacketGenerator
from ns.packet.packet import Packet
from ns.packet.tcp_sink import TCPSink
from tests.packet.test_bbr_generator import CaptureSink, DummyCC


def sender_for(*, size=1024, mss=512, cwnd=4096, pacing=0, finish=10,
               arrival=None, sizes=None):
    env = simpy.Environment()
    flow = Flow(7, "src", "dst", size=size, finish_time=finish,
                typ=AppType.VIDEO if arrival else AppType.BULK_TRANSFER,
                arrival_dist=arrival, size_dist=sizes)
    cc = DummyCC(cwnd)
    cc.mss = mss
    cc.pacing_rate = pacing
    sender = BBRPacketGenerator(env, flow, cc, debug=False)
    capture = CaptureSink(env)
    sender.out = capture
    return env, sender, capture


def ack(frontier, fid=10007, time=0):
    packet = Packet(time, 40, 0, flow_id=fid)
    packet.ack = frontier
    return packet


def test_controller_mss_and_integer_window_limit():
    env, sender, capture = sender_for(size=601, mss=300, cwnd=600.9)
    env.run(until=0.01)
    assert [(p.packet_id, p.size) for p in capture.packets] == [(0, 300), (300, 300)]
    sender.put(ack(300))
    env.run(until=0.02)
    assert [(p.packet_id, p.size) for p in capture.packets][-1] == (600, 1)
    assert all(isinstance(p.size, int) for p in capture.packets)


@pytest.mark.parametrize("frontier,fid", [(1025, 10007), (-1, 10007),
                                              (1.5, 10007), (512, 10008),
                                              (512, 7), (None, 10007)])
def test_invalid_ack_cannot_change_transport_or_controller(frontier, fid):
    env, sender, _ = sender_for()
    env.run(until=0.01)
    original = (sender.last_ack, sender.packet_in_flight, sender.rto,
                sender.congestion_control.C.delivered)
    sender.put(ack(frontier, fid))
    assert (sender.last_ack, sender.packet_in_flight, sender.rto,
            sender.congestion_control.C.delivered) == original
    assert sender.congestion_control.calls == []


def test_partial_ack_frees_exact_bytes_and_retransmits_suffix():
    env, sender, capture = sender_for(size=512)
    env.run(until=0.01)
    original = capture.packets[0]
    sender.put(ack(123))
    assert sender.packet_in_flight == 389
    assert sender.congestion_control.C.delivered == 123
    sender.timeout_callback()
    retransmitted = capture.packets[-1]
    assert (retransmitted.packet_id, retransmitted.size) == (123, 389)
    assert (original.packet_id, original.size, original.time) == (0, 512, 0)
    sender.put(ack(512))
    assert sender.packet_in_flight == 0
    assert sender.congestion_control.C.delivered == 512
    assert sender.timer is None


def test_zero_time_flight_and_duplicate_acks_never_fabricate_delivery():
    env, sender, _ = sender_for(size=512)
    env.run(until=0.01)
    sender.put(ack(0))
    sender.put(ack(0))
    assert sender.congestion_control.C.delivered == 0
    assert sender.packet_in_flight == 512
    sender.put(ack(512))
    assert sender.congestion_control.C.delivered == 512
    assert sender.packet_in_flight == 0
    sender.put(ack(512))
    sender.put(ack(0))
    assert sender.dupack == 0
    assert sender.congestion_control.C.delivered == 512


def test_third_duplicate_retransmits_once_and_partial_recovery_retransmits_next():
    env, sender, capture = sender_for(size=2048)
    env.run(until=0.01)
    for _ in range(2):
        sender.put(ack(0))
    assert len(capture.packets) == 4
    sender.put(ack(0))
    sender.put(ack(0))
    assert [p.packet_id for p in capture.packets] == [0, 512, 1024, 1536, 0]
    assert sender.congestion_control.C.delivered == 0
    sender.put(ack(512))
    env.run(until=0.02)
    assert capture.packets[-1].packet_id == 512
    assert not any(c[0] == "dupack_over" for c in sender.congestion_control.calls)
    sender.put(ack(2048))
    assert sum(c[0] == "dupack_over" for c in sender.congestion_control.calls) == 1
    assert sender.timer is None


def test_timer_restarts_from_advancing_ack_and_backoff_stays_after_ambiguous_ack():
    env, sender, capture = sender_for(size=1024)
    env.run(until=0.1)
    sender.put(ack(512))
    assert sender.timer.timer_expiry == pytest.approx(env.now + sender.rto)
    env.run(until=1.11)
    assert capture.packets[-1].packet_id == 512
    backed_off = sender.rto
    sender.put(ack(1024, time=env.now))
    assert sender.rto == backed_off
    assert sender.timer is None


def test_rtt_comes_from_sender_state_and_uses_absolute_deviation():
    env, sender, _ = sender_for(size=1024, cwnd=512)
    env.run(until=0.1)
    sender.put(ack(512, time=-1000))
    assert sender.rtt_estimate == pytest.approx(0.1)
    env.run(until=0.3)
    sender.put(ack(1024, time=-1000))
    assert sender.rtt_estimate == pytest.approx(0.1125)
    assert sender.est_deviation == pytest.approx(0.0625)


def test_synchronous_ack_can_complete_new_send_and_timeout():
    env, sender, capture = sender_for(size=512)
    receiver = TCPSink(env, debug=False)
    receiver.out = sender
    sender.out = receiver
    env.run(until=0.01)
    assert sender.next_seq == sender.last_ack == 512
    assert sender.timer is None
    assert sender.packet_in_flight == 0

    env, sender, capture = sender_for(size=512)
    env.run(until=0.01)
    receiver = TCPSink(env, debug=False)
    receiver.out = sender
    sender.out = receiver
    sender.timeout_callback()
    assert sender.timer is None
    assert sender.segment_state == {}
    env.run(until=2)
    assert receiver.packets_received[7] == 1


def test_exclusive_deadline_is_rechecked_after_pacing_and_cwnd_waits():
    env, sender, capture = sender_for(size=1024, pacing=512, finish=1)
    env.run(until=1.01)
    assert [p.packet_id for p in capture.packets if p.time == 0] == [0, 0]
    assert sender.next_seq == 512
    assert not sender.action.is_alive
    sender.put(ack(512))
    assert sender.timer is None

    env, sender, capture = sender_for(size=1024, cwnd=512, finish=0.2)
    env.run(until=0.21)
    assert not sender.action.is_alive
    sender.put(ack(512))
    env.run(until=0.3)
    assert sender.next_seq == 512


def test_application_arrivals_are_sampled_once_and_volume_is_capped():
    draws = []
    def arrival():
        draws.append(True)
        return 0.1
    env, sender, capture = sender_for(size=650, arrival=arrival, sizes=lambda: 400)
    env.run(until=0.25)
    assert [(p.time, p.size) for p in capture.packets] == [(0.1, 400), (0.2, 250)]
    assert len(draws) == 2
    assert sender.congestion_control.C.write_seq == 650


@pytest.mark.parametrize("size", [0, -1, 0.5])
def test_invalid_application_chunks_are_rejected_without_spin(size):
    env, sender, _ = sender_for(size=650, arrival=lambda: 0.1, sizes=lambda: size)
    with pytest.raises(ValueError):
        env.run(until=0.2)


def test_unbounded_bulk_flow_can_start_without_finish_or_size():
    env, sender, capture = sender_for(size=None, cwnd=512, finish=None)
    env.run(until=0.01)
    assert [p.size for p in capture.packets] == [512]
    assert sender.packet_in_flight == 512


def test_rate_sampler_counts_a_zero_time_packet_once():
    from ns.packet.rate_sample import Connection, RateSample
    connection = Connection()
    sample = RateSample()
    packet = Packet(0, 123, 0)
    sample.send_packet(packet, connection, 0, 0)
    sample.updaterate_sample(packet, connection, 0.1)
    sample.updaterate_sample(packet, connection, 0.2)
    assert connection.delivered == 123
    assert sample.ack_elapsed == pytest.approx(0.1)


@pytest.mark.parametrize("lose_ack", [False, True])
def test_one_data_or_ack_loss_drains_after_new_data_deadline(lose_ack):
    from ns.port.wire import Wire
    env, sender, capture = sender_for(size=512 if lose_ack else 700, finish=0.05)
    receiver = TCPSink(env, debug=False)
    down = Wire(env, lambda: 0.01)
    up = Wire(env, lambda: 0.01)
    attempts = []
    dropped = []

    class LoseOnce:
        def __init__(self, output):
            self.output = output

        def put(self, packet):
            if not dropped:
                dropped.append(packet)
            else:
                self.output.put(packet)

    class RecordData:
        def put(self, packet):
            attempts.append(packet)
            down.put(packet)

    sender.out = RecordData()
    down.out = receiver if lose_ack else LoseOnce(receiver)
    receiver.out = LoseOnce(up) if lose_ack else up
    up.out = sender
    env.run(until=2)
    assert sender.next_seq == sender.last_ack == receiver.next_seq_expected == (512 if lose_ack else 700)
    assert sender.packet_in_flight == 0
    assert sender.congestion_control.C.delivered == (512 if lose_ack else 700)
    assert sender.timer is None
    assert sender.sent_packets == sender.segment_state == {}
    count = len(attempts)
    env.run(until=5)
    assert len(attempts) == count


def test_pacing_keeps_original_byte_rate_units_and_short_tail_interval():
    env, sender, capture = sender_for(size=700, mss=300, pacing=3000)
    env.run(until=0.21)
    assert [(p.packet_id, p.size) for p in capture.packets] == [
        (0, 300), (300, 300), (600, 100),
    ]
    assert [p.time for p in capture.packets] == pytest.approx([0, 0.1, 0.2])
    assert sender.congestion_control.next_departure_time == pytest.approx(
        0.2 + 100 / 3000,
    )


def test_start_time_is_absolute_even_when_environment_starts_later():
    env = simpy.Environment(initial_time=5)
    flow = Flow(7, "src", "dst", size=1, start_time=6, finish_time=7)
    sender = BBRPacketGenerator(env, flow, DummyCC(), debug=False)
    capture = CaptureSink(env)
    sender.out = capture
    env.run(until=6.1)
    assert capture.packets[0].time == 6


@pytest.mark.parametrize("ack_first", [False, True])
def test_ack_timeout_same_timestamp_follows_simpy_insertion_order(ack_first):
    env, sender, capture = sender_for(size=512)

    def acknowledge():
        yield env.timeout(1)
        sender.put(ack(512))

    if ack_first:
        env.process(acknowledge())
    env.run(until=0.01)
    if not ack_first:
        # Create this event at t=.01 with a .99 delay, at the same timer deadline.
        def acknowledge_later():
            yield env.timeout(0.99)
            sender.put(ack(512))
        env.process(acknowledge_later())
    env.run(until=1.01)
    assert len(capture.packets) == (1 if ack_first else 2)
    assert sender.last_ack == 512
    assert sender.timer is None


def test_continuous_application_size_is_floored_once_to_whole_bytes():
    env, sender, capture = sender_for(size=3, arrival=lambda: 0.1, sizes=lambda: 1.9)
    env.run(until=0.31)
    assert [(p.packet_id, p.size) for p in capture.packets] == [(0, 1), (1, 1), (2, 1)]
    assert sender.send_buffer == 3


@pytest.mark.parametrize("interval", [0, -1, float("inf"), float("nan")])
def test_invalid_application_interval_is_rejected_without_spin(interval):
    env, sender, _ = sender_for(size=512, arrival=lambda: interval)
    with pytest.raises(ValueError):
        env.run(until=0.01)


def test_subbyte_window_waits_and_deadline_ends_the_process():
    env, sender, capture = sender_for(size=1, cwnd=0.9, finish=0.1)
    env.run(until=0.11)
    assert capture.packets == []
    assert sender.next_seq == 0
    assert not sender.action.is_alive


def test_synchronous_burst_loss_recovery_drains_without_recursive_ack_stack():
    from collections import Counter
    from ns.flow.bbr import BBR

    env = simpy.Environment()
    flow = Flow(7, "src", "dst", size=65536, finish_time=1)
    sender = BBRPacketGenerator(
        env, flow, BBR(mss=128, cwnd=65536), debug=False,
    )
    receiver = TCPSink(env, debug=False)
    receiver.out = sender
    attempts = Counter()

    class LoseFirstBurst:
        def put(self, packet):
            attempts[packet.packet_id] += 1
            if packet.packet_id < 65152 and attempts[packet.packet_id] == 1:
                return
            receiver.put(packet)

    sender.out = LoseFirstBurst()
    env.run(until=2)
    assert sender.last_ack == sender.next_seq == receiver.next_seq_expected == 65536
    assert sender.packet_in_flight == 0
    assert sender.congestion_control.C.delivered == 65536
    assert sender.timer is None
    assert sender.segment_state == sender.sent_packets == {}
    assert attempts == Counter({seq: 2 if seq < 65152 else 1
                                for seq in range(0, 65536, 128)})
    completed_attempts = attempts.copy()
    env.run(until=5)
    assert attempts == completed_attempts


def test_ack_can_retire_a_deferred_recovery_attempt_before_forwarding():
    env, sender, capture = sender_for(size=2048)
    env.run(until=0.01)
    for _ in range(3):
        sender.put(ack(0))
    sender.put(ack(512))
    sender.put(ack(2048))
    env.run(until=0.02)
    assert [packet.packet_id for packet in capture.packets] == [0, 512, 1024, 1536, 0]
    assert sender.timer is None
    assert sender.segment_state == {}


def test_partial_ack_replaces_pending_recovery_with_only_its_remaining_suffix():
    env, sender, capture = sender_for(size=2048)
    env.run(until=0.01)
    for _ in range(3):
        sender.put(ack(0))
    sender.put(ack(512))
    sender.put(ack(600))
    env.run(until=0.02)
    assert [(packet.packet_id, packet.size) for packet in capture.packets[-2:]] == [
        (0, 512), (600, 424),
    ]
    assert sender.segment_state[600].retransmit_count == 1
    assert sender.congestion_control.C.lost == 512 + 424


def test_timeout_supersedes_a_pending_partial_recovery_attempt():
    env, sender, capture = sender_for(size=2048)
    env.run(until=0.01)
    for _ in range(3):
        sender.put(ack(0))
    sender.put(ack(512))
    sender.timeout_callback()
    env.run(until=0.02)
    assert [packet.packet_id for packet in capture.packets] == [
        0, 512, 1024, 1536, 0, 512,
    ]
    assert sender.segment_state[512].retransmit_count == 1
