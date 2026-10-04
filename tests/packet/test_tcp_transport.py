"""Transport invariants independent of Reno/CUBIC's window update formulas."""

import pytest
import simpy

from ns.flow.flow import Flow
from ns.packet.packet import Packet
from ns.packet.tcp_generator import TCPPacketGenerator


class TransportCC:
    """Record feedback; additional duplicate ACKs grant one segment of credit."""

    def __init__(self, *, mss=512, cwnd=4096):
        self.mss = mss
        self.cwnd = cwnd
        self.events = []
        self.context = []

    def set_before_control(self, now, bytes_in_flight):
        self.context.append((now, bytes_in_flight))

    def ack_received(self, rtt, now):
        self.events.append(("ack", rtt, now))

    def partial_ack_received(self, acknowledged_bytes, now):
        self.events.append(("partial", acknowledged_bytes, now))

    def consecutive_dupacks_received(self):
        self.events.append(("fast",))

    def more_dupacks_received(self):
        self.events.append(("extra",))
        self.cwnd += self.mss

    def dupack_over(self):
        self.events.append(("exit",))

    def timer_expired(self):
        self.events.append(("timeout",))


def ack(sequence, flow_id=10001):
    packet = Packet(0, 40, sequence, flow_id=flow_id)
    packet.ack = sequence
    return packet


class Attempts:
    def __init__(self, env):
        self.env = env
        self.records = []

    def put(self, packet):
        self.records.append((self.env.now, packet))


def sender_for(env, size, *, cc=None, finish_time=10, **flow_options):
    sender = TCPPacketGenerator(
        env,
        Flow(1, "src", "dst", size=size, finish_time=finish_time, **flow_options),
        TransportCC() if cc is None else cc,
    )
    output = Attempts(env)
    sender.out = output
    return sender, output


def test_controller_mss_and_short_tail_are_respected():
    env = simpy.Environment()
    sender, output = sender_for(env, 257, cc=TransportCC(mss=100))
    env.run(until=0.01)
    assert [(p.packet_id, p.size) for _, p in output.records] == [
        (0, 100), (100, 100), (200, 57)
    ]
    assert sender.next_seq == 257


def test_fractional_window_never_emits_fractional_bytes():
    env = simpy.Environment()
    sender, output = sender_for(env, 1024, cc=TransportCC(cwnd=512.75))
    env.run(until=0.01)
    assert [(p.packet_id, p.size) for _, p in output.records] == [(0, 512)]
    assert sender.next_seq == 512


def test_application_burst_cannot_exceed_flow_size():
    env = simpy.Environment()
    sender, output = sender_for(env, 300, size_dist=lambda: 1200.75)
    env.run(until=0.01)
    assert [(p.packet_id, p.size) for _, p in output.records] == [(0, 300)]
    assert sender.send_buffer == 300


def test_application_arrival_at_finish_generates_no_new_data():
    env = simpy.Environment()
    sender, output = sender_for(
        env, 512, finish_time=0.25, arrival_dist=lambda: 0.25
    )
    env.run(until=0.3)
    assert output.records == []
    assert not sender.action.is_alive


def test_window_blocked_generator_finishes_but_emitted_bytes_still_retransmit():
    env = simpy.Environment()
    sender, output = sender_for(
        env, 1024, cc=TransportCC(cwnd=512), finish_time=0.25
    )
    env.run(until=1.1)
    assert not sender.action.is_alive
    assert [(t, p.packet_id) for t, p in output.records] == [(0, 0), (1, 0)]
    sender.put(ack(512))
    env.run(until=4)
    assert sender.next_seq == 512
    assert len(output.records) == 2


@pytest.mark.parametrize("sequence, flow_id", [(1025, 10001), (-1, 10001),
                                               (512, 10002), (512, 1),
                                               (100.5, 10001), (None, 10001),
                                               (True, 10001)])
def test_invalid_ack_does_not_change_transport_or_controller(sequence, flow_id):
    env = simpy.Environment()
    sender, output = sender_for(env, 1024)
    env.run(until=0.01)
    before = (sender.last_ack, sender.dupack, set(sender.segment_state), sender.rto)
    sender.put(ack(sequence, flow_id))
    assert (sender.last_ack, sender.dupack, set(sender.segment_state), sender.rto) == before
    assert sender.congestion_control.events == []
    assert len(output.records) == 2


def test_stale_ack_cannot_rewind_frontier_or_deflate_recovery():
    env = simpy.Environment()
    sender, _ = sender_for(env, 2048)
    env.run(until=0.01)
    sender.put(ack(512))
    sender.put(ack(512))
    before = list(sender.congestion_control.events)
    sender.put(ack(0))
    assert sender.last_ack == 512
    assert sender.dupack == 1
    assert sender.congestion_control.events == before


def test_fast_retransmit_once_then_duplicate_ack_clocks_new_data():
    env = simpy.Environment()
    sender, output = sender_for(env, 4096, cc=TransportCC(cwnd=2048))
    env.run(until=0.01)
    for _ in range(5):
        sender.put(ack(0))
        env.run(until=env.now + 0.01)
    assert [p.packet_id for _, p in output.records] == [0, 512, 1024, 1536,
                                                      0, 2048, 2560]
    assert sender.congestion_control.events == [("fast",), ("extra",), ("extra",)]


def test_partial_recovery_ack_retransmits_next_hole_without_exiting():
    env = simpy.Environment()
    sender, output = sender_for(env, 2048)
    env.run(until=0.01)
    for _ in range(3):
        sender.put(ack(0))
    sender.put(ack(512))
    sender.put(ack(1024))
    assert [p.packet_id for _, p in output.records] == [0, 512, 1024, 1536,
                                                      0, 512, 1024]
    assert [e[0] for e in sender.congestion_control.events] == ["fast", "partial", "partial"]
    sender.put(ack(2048))
    assert [e[0] for e in sender.congestion_control.events] == ["fast", "partial", "partial", "exit"]
    assert sender.segment_state == {}


def test_partial_segment_ack_retransmits_only_unacknowledged_suffix():
    env = simpy.Environment()
    sender, output = sender_for(env, 512)
    env.run(until=0.2)
    sender.put(ack(128))
    env.run(until=1.21)
    _, retransmission = output.records[-1]
    assert (retransmission.packet_id, retransmission.size) == (128, 384)
    assert retransmission.time == 0
    sender.put(ack(512))
    assert sender.segment_state == {}


def test_only_oldest_segment_times_out_and_rto_backs_off_globally():
    env = simpy.Environment()
    sender, output = sender_for(env, 1536)
    env.run(until=3.01)
    assert [(t, p.packet_id) for t, p in output.records] == [
        (0, 0), (0, 512), (0, 1024), (1, 0), (3, 0)
    ]
    assert sender.rto == 4
    assert sender.congestion_control.events == [("timeout",), ("timeout",)]


def test_new_cumulative_ack_restarts_timer_for_remaining_data():
    env = simpy.Environment()
    sender, output = sender_for(env, 1024)
    env.run(until=0.75)
    sender.put(ack(512))
    env.run(until=1.01)
    assert len(output.records) == 2
    # RTT=.75 => first RTO = .75 + 4*(.75/2) = 2.25.
    env.run(until=3.01)
    assert [(t, p.packet_id) for t, p in output.records][-1] == (3, 512)


def test_fast_retransmit_restarts_oldest_timer():
    env = simpy.Environment()
    sender, output = sender_for(env, 2048)
    env.run(until=0.75)
    for _ in range(3):
        sender.put(ack(0))
    env.run(until=1.1)
    assert len(output.records) == 5
    env.run(until=1.76)
    assert [(t, p.packet_id) for t, p in output.records][-1] == (1.75, 0)


def test_synchronous_receiver_ack_observes_registered_state_and_cancels_timer():
    env = simpy.Environment()
    sender, output = sender_for(env, 768, cc=TransportCC(cwnd=512))

    class ImmediateAck:
        def put(self, packet):
            output.put(packet)
            sender.put(ack(packet.packet_id + packet.size))

    sender.out = ImmediateAck()
    env.run(until=4)
    assert [p.size for _, p in output.records] == [512, 256]
    assert sender.last_ack == sender.next_seq == 768
    assert sender.segment_state == sender.sent_packets == sender.timers == {}


def test_cumulative_ack_is_rtt_ambiguous_and_completion_ignores_late_ack():
    env = simpy.Environment()
    sender, output = sender_for(env, 1024)
    env.run(until=0.2)
    sender.put(ack(1024))
    assert sender.smoothed_rtt == 0
    before = list(sender.congestion_control.events)
    for _ in range(4):
        sender.put(ack(1024))
    env.run(until=3)
    assert sender.congestion_control.events == before
    assert len(output.records) == 2


def test_zero_rtt_is_an_initialized_sample_not_a_sentinel():
    env = simpy.Environment()
    sender, output = sender_for(env, 1024, cc=TransportCC(cwnd=512))

    class FirstAckImmediate:
        def put(self, packet):
            output.put(packet)
            if packet.packet_id == 0:
                sender.put(ack(512))

    sender.out = FirstAckImmediate()
    env.run(until=0.2)
    sender.put(ack(1024))
    assert sender.smoothed_rtt == pytest.approx(0.2 / 8)
    assert sender.rtt_var == pytest.approx(0.2 / 4)


def test_start_time_is_absolute_when_environment_already_advanced():
    env = simpy.Environment(initial_time=5)
    sender, output = sender_for(env, 512, start_time=6, finish_time=7)
    env.run(until=6.1)
    assert [(t, p.packet_id) for t, p in output.records] == [(6, 0)]


def test_missing_finish_time_allows_finite_flow_to_complete():
    env = simpy.Environment()
    sender, output = sender_for(env, 257, finish_time=None)
    env.run(until=0.01)
    assert [p.size for _, p in output.records] == [257]


def test_duplicate_ack_after_partial_recovery_grants_credit_without_reloss():
    env = simpy.Environment()
    sender, output = sender_for(env, 4096, cc=TransportCC(cwnd=2048))
    env.run(until=0.01)
    for _ in range(3):
        sender.put(ack(0))
    sender.put(ack(512))
    sender.put(ack(512))
    assert sender.congestion_control.events == [("fast",), ("partial", 512, 0.01),
                                               ("extra",)]
    env.run(until=0.02)
    assert [p.packet_id for _, p in output.records] == [0, 512, 1024, 1536,
                                                      0, 512, 2048, 2560]


def test_only_actual_recovery_exit_deflates_controller():
    env = simpy.Environment()
    sender, _ = sender_for(env, 1024)
    env.run(until=0.01)
    sender.put(ack(0))
    sender.put(ack(0))
    sender.put(ack(512))
    assert [event[0] for event in sender.congestion_control.events] == ["ack"]


def test_feedback_context_uses_outstanding_bytes_before_ack():
    env = simpy.Environment()
    sender, _ = sender_for(env, 1024)
    env.run(until=0.2)
    sender.put(ack(128))
    assert sender.congestion_control.context == [(0.2, 1024)]
    assert sender.bytes_in_flight == 896


@pytest.mark.parametrize("ack_first", [True, False])
def test_ack_timeout_same_timestamp_follows_simpy_order_and_stays_complete(ack_first):
    env = simpy.Environment()
    sender, output = sender_for(env, 512)

    def feedback():
        yield env.timeout(1 - env.now)
        sender.put(ack(512))

    if ack_first:
        # This process schedules its ACK before the timer's initial process runs.
        env.process(feedback())
    else:
        env.run(until=0.01)
        env.process(feedback())
    env.run(until=4)
    assert len(output.records) == (1 if ack_first else 2)
    assert sender.last_ack == sender.next_seq == 512
    assert sender.segment_state == sender.timers == {}


def test_timeout_retransmission_can_be_acknowledged_synchronously():
    env = simpy.Environment()
    sender, output = sender_for(env, 512)

    class LostOriginal:
        def put(self, packet):
            output.put(packet)
            if len(output.records) == 2:
                sender.put(ack(512))

    sender.out = LostOriginal()
    env.run(until=4)
    assert [(t, p.packet_id) for t, p in output.records] == [(0, 0), (1, 0)]
    assert sender.rto == 2
    assert sender.segment_state == sender.timers == {}


def test_repeated_loss_caps_timeout_at_sixty_seconds():
    env = simpy.Environment()
    sender, output = sender_for(env, 512)
    env.run(until=123.01)
    assert [t for t, _ in output.records] == [0, 1, 3, 7, 15, 31, 63, 123]
    assert sender.rto == 60


def test_stable_long_rtt_retains_one_millisecond_estimator_granularity():
    env = simpy.Environment()
    sender, output = sender_for(
        env, 3500, cc=TransportCC(mss=100, cwnd=100), finish_time=100
    )
    # A configured initial RTO above the known two-second RTT avoids startup
    # ambiguity. Repeated equal samples make variation smaller than G/4.
    sender.rto = 3

    class DelayedAck:
        def put(self, packet):
            output.put(packet)
            env.process(self.feedback(packet.packet_id + packet.size))

        def feedback(self, sequence):
            yield env.timeout(2)
            sender.put(ack(sequence))

    sender.out = DelayedAck()
    env.run(until=70.01)
    assert len(output.records) == 35
    assert sender.last_ack == 3500
    assert sender.smoothed_rtt == 2
    assert sender.rto == pytest.approx(2.001)
    assert all(event[0] == "ack" for event in sender.congestion_control.events)


def test_learned_rto_also_obeys_sixty_second_ceiling():
    env = simpy.Environment()
    sender, _ = sender_for(env, 512)
    sender.rto = 30
    env.run(until=25)
    sender.put(ack(512))
    assert sender.smoothed_rtt == 25
    assert sender.rto == 60
