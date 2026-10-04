"""Observable transport behavior through a real TCPSink and explicit paths.

Passive control isolates TCP mechanics from controller window-growth formulas.
Losses and delays identify particular attempts; no random seed is involved.
"""

import pytest
import simpy

from ns.flow.flow import AppType, Flow
from ns.packet.bbr_generator import BBRPacketGenerator
from ns.packet.tcp_generator import TCPPacketGenerator
from ns.packet.tcp_sink import TCPSink


class PassiveControl:
    """Hold a byte window and record loss signals for either sender API."""

    def __init__(self, mss, cwnd):
        self.mss = mss
        self.cwnd = cwnd
        self.pacing_rate = 0
        self.next_departure_time = 0
        self.events = []

    def set_before_control(self, now, flight):
        pass

    def ack_received(self, rtt, now):
        self.events.append("ack")

    def timer_expired(self, packet=None):
        self.events.append("timeout")

    def consecutive_dupacks_received(self, packet=None):
        self.events.append("fast")

    def more_dupacks_received(self, packet=None):
        self.events.append("extra")

    def partial_ack_received(self, acknowledged_bytes, now):
        self.events.append("partial")

    def dupack_over(self):
        self.events.append("exit")


class ExplicitPath:
    """Capture attempts, then deliver zero or more copies after specified waits."""

    def __init__(self, env, output, schedule):
        self.env = env
        self.output = output
        self.schedule = schedule
        self.attempts = []
        self.arrivals = []

    def put(self, packet):
        index = len(self.attempts)
        self.attempts.append((self.env.now, packet))
        for delay in self.schedule(packet, index):
            self.env.process(self.deliver(packet, delay))

    def deliver(self, packet, delay):
        """Wait from path entry; each scheduled copy arrives once."""
        yield self.env.timeout(delay)
        self.arrivals.append((self.env.now, packet))
        self.output.put(packet)


@pytest.fixture(params=[TCPPacketGenerator, BBRPacketGenerator],
                ids=["tcp", "bbr"])
def sender_type(request):
    return request.param


def connection(sender_type, *, size, mss=300, cwnd=4096, finish=0.05):
    env = simpy.Environment()
    cc = PassiveControl(mss, cwnd)
    sender = sender_type(
        env, Flow(7, "src", "dst", size=size, finish_time=finish), cc,
        debug=False,
    )
    receiver = TCPSink(env)
    return env, sender, receiver


def assert_drained(env, sender, receiver, data, expected):
    assert sender.next_seq == sender.last_ack == expected
    assert receiver.next_seq_expected == receiver.bytes_delivered == expected
    assert sender.segment_state == sender.sent_packets == {}
    assert sender.timer is None or sender.timer.stopped
    flight = (sender.bytes_in_flight if isinstance(sender, TCPPacketGenerator)
              else sender.packet_in_flight)
    assert flight == 0
    count = len(data.attempts)
    # Observe beyond backed-off deadlines to detect lingering retransmissions.
    env.run(until=5)
    assert len(data.attempts) == count


def test_reorder_duplicate_and_custom_mss_short_tail(sender_type):
    env, sender, receiver = connection(sender_type, size=701)
    delays = {0: (0.02,), 300: (0.01, 0.012), 600: (0.03,)}
    data = ExplicitPath(
        env, receiver, lambda packet, _: delays.get(packet.packet_id, (0.03,))
    )
    feedback = ExplicitPath(env, sender, lambda *_: (0.005,))
    sender.out = data
    receiver.out = feedback
    env.run(until=0.1)

    assert [(p.packet_id, p.size) for _, p in data.attempts] == [
        (0, 300), (300, 300), (600, 101)
    ]
    assert [p.packet_id for _, p in data.arrivals] == [300, 300, 0, 600]
    assert [p.ack for _, p in feedback.attempts] == [0, 0, 600, 701]
    assert receiver.packets_received[7] == 4
    assert receiver.bytes_received[7] == 1001
    assert receiver.waits[7] == pytest.approx([0.01, 0.012, 0.02, 0.03])
    assert not any(event in sender.congestion_control.events
                   for event in ("timeout", "fast"))
    assert_drained(env, sender, receiver, data, 701)


def test_data_loss_retransmits_gap_after_new_data_deadline(sender_type):
    env, sender, receiver = connection(sender_type, size=601)
    # Drop the first attempt for [300,600); the short tail arrives beyond a gap.
    data = ExplicitPath(
        env, receiver, lambda packet, index: () if index == 1 else (0.01,)
    )
    feedback = ExplicitPath(env, sender, lambda *_: (0.01,))
    sender.out = data
    receiver.out = feedback
    env.run(until=1.1)

    assert [(p.packet_id, p.size) for _, p in data.attempts] == [
        (0, 300), (300, 300), (600, 1), (300, 300)
    ]
    assert [time for time, _ in data.attempts] == pytest.approx([0, 0, 0, 1.02])
    assert [p.ack for _, p in feedback.attempts] == [300, 300, 601]
    assert receiver.bytes_received[7] == 601
    assert receiver.waits[7] == pytest.approx([0.01, 0.01, 1.03])
    original, retransmission = data.attempts[1][1], data.attempts[3][1]
    assert retransmission is not original
    assert original.time == retransmission.time == 0
    assert sender.congestion_control.events.count("timeout") == 1
    assert not sender.action.is_alive
    assert_drained(env, sender, receiver, data, 601)


def test_ack_loss_repeats_physical_delivery_but_not_application_bytes(sender_type):
    env, sender, receiver = connection(sender_type, size=123)
    data = ExplicitPath(env, receiver, lambda *_: (0.01,))
    feedback = ExplicitPath(env, sender, lambda packet, index: (
        () if index == 0 else (0.01,)
    ))
    sender.out = data
    receiver.out = feedback
    env.run(until=1.1)

    assert [time for time, _ in data.attempts] == [0, 1]
    assert [p.ack for _, p in feedback.attempts] == [123, 123]
    assert receiver.packets_received[7] == 2
    assert receiver.bytes_received[7] == 246
    assert receiver.waits[7] == pytest.approx([0.01, 1.01])
    assert sender.rto == 2  # Karn: the retransmitted ACK supplies no RTT sample.
    assert_drained(env, sender, receiver, data, 123)


def test_synchronous_receiver_ack_cancels_registered_new_send_timer(sender_type):
    env, sender, receiver = connection(sender_type, size=701, cwnd=300)
    data = ExplicitPath(env, receiver, lambda *_: ())

    class ImmediateReceiver:
        def put(self, packet):
            data.put(packet)
            receiver.put(packet)

    sender.out = ImmediateReceiver()
    receiver.out = sender
    env.run(until=0.1)
    assert [(p.packet_id, p.size) for _, p in data.attempts] == [
        (0, 300), (300, 300), (600, 101)
    ]
    assert receiver.bytes_received[7] == 701
    assert sender.congestion_control.events == ["ack", "ack", "ack"]
    assert_drained(env, sender, receiver, data, 701)


@pytest.mark.parametrize("ack_first", [True, False], ids=["ack-first", "timer-first"])
def test_receiver_ack_at_timeout_timestamp_obeys_local_simpy_order(
    sender_type, ack_first
):
    env, sender, receiver = connection(sender_type, size=123)
    # Hold physical data so the real receiver emits its ACK exactly at t=1.
    data = ExplicitPath(env, receiver, lambda *_: ())
    sender.out = data
    receiver.out = sender

    def release_original():
        """Wait until the exact timer deadline and deliver the held original."""
        yield env.timeout(1 - env.now)
        receiver.put(data.attempts[0][1])

    if ack_first:
        # Schedule receiver arrival before the timer process schedules its wait.
        env.process(release_original())
    else:
        env.run(until=0.01)
        env.process(release_original())
    env.run(until=1.1)

    assert len(data.attempts) == (1 if ack_first else 2)
    assert sender.congestion_control.events.count("timeout") == int(not ack_first)
    assert receiver.bytes_received[7] == 123
    assert_drained(env, sender, receiver, data, 123)


def test_exclusive_finish_blocks_new_bytes_but_recovers_outstanding_data(sender_type):
    env, sender, receiver = connection(sender_type, size=601, cwnd=300, finish=0.5)
    data = ExplicitPath(env, receiver, lambda packet, index: (
        () if index == 0 else (0.01,)
    ))
    feedback = ExplicitPath(env, sender, lambda *_: (0.01,))
    sender.out = data
    receiver.out = feedback
    env.run(until=0.6)
    assert not sender.action.is_alive
    assert sender.next_seq == 300
    assert receiver.bytes_delivered == 0
    env.run(until=1.1)
    assert [(time, p.packet_id, p.size) for time, p in data.attempts] == [
        (0, 0, 300), (1, 0, 300)
    ]
    assert_drained(env, sender, receiver, data, 300)


def test_ack_at_exclusive_finish_cannot_release_new_application_bytes(sender_type):
    env, sender, receiver = connection(sender_type, size=601, cwnd=300, finish=0.5)
    data = ExplicitPath(env, receiver, lambda *_: (0,))
    feedback = ExplicitPath(env, sender, lambda *_: (0.5,))
    sender.out = data
    receiver.out = feedback
    env.run(until=0.6)
    assert [p.packet_id for _, p in data.attempts] == [0]
    assert sender.last_ack == 300
    assert not sender.action.is_alive
    assert_drained(env, sender, receiver, data, 300)


def test_application_arrival_at_exclusive_finish_sends_no_data(sender_type):
    env = simpy.Environment()
    flow = Flow(
        7, "src", "dst", size=123, finish_time=0.5, typ=AppType.VIDEO,
        arrival_dist=lambda: 0.5, size_dist=lambda: 123,
    )
    sender = sender_type(env, flow, PassiveControl(300, 300), debug=False)
    receiver = TCPSink(env)
    data = ExplicitPath(env, receiver, lambda *_: (0,))
    sender.out = data
    receiver.out = sender
    env.run(until=0.6)
    assert data.attempts == []
    assert not sender.action.is_alive
    assert_drained(env, sender, receiver, data, 0)
