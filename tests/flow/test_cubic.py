"""Feedback sequences for the floating-point Days educational CUBIC model."""

import math

import pytest
import simpy

from ns.flow.cubic import TCPCubic
from ns.flow.flow import Flow
from ns.packet.tcp_generator import TCPPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.port.wire import Wire


def test_beta_is_the_retained_window_fraction():
    cubic = TCPCubic(mss=1000, cwnd=20000)
    assert cubic.beta == 0.7
    cubic.consecutive_dupacks_received()
    assert cubic.ssthresh == 14000
    assert cubic.cwnd == 14000  # CUBIC does not use Reno's three-MSS inflation.


@pytest.mark.parametrize("ack_bytes, expected", [(123, 2000), (1000, 2000), (2123, 4000)])
def test_slow_start_counts_acknowledged_segments(ack_bytes, expected):
    cubic = TCPCubic(mss=1000, cwnd=1000, ssthresh=100000)
    cubic.ack_received(rtt=0.1, acknowledged_bytes=ack_bytes)
    assert cubic.cwnd == expected


def test_slow_start_enters_avoidance_at_the_crossing_ack_time():
    cubic = TCPCubic(mss=1000, cwnd=1000, ssthresh=2500)
    cubic.ack_received(rtt=0.1, current_time=3, acknowledged_bytes=2000)
    assert cubic.cwnd == 3000  # The Days CUBIC crossing is not clipped to ssthresh.
    assert cubic.epoch_start == 3
    assert cubic.W_max == 3
    assert cubic.K == 0


def test_epoch_at_time_zero_is_retained_on_the_next_ack():
    cubic = TCPCubic(mss=1000, cwnd=10000, ssthresh=2000)
    cubic.tcp_friendliness = False  # isolate the cubic curve from its friendly branch
    cubic.ack_received(rtt=0.1, current_time=0)
    # First no-loss epoch: Wmax=10, K=0, target=10+0.4*(0.1)^3.
    assert cubic.cwnd == pytest.approx(10000.04, rel=1e-12)
    cubic.ack_received(rtt=0.1, current_time=1)
    assert cubic.epoch_start == 0
    assert cubic.cwnd == pytest.approx(10000.04 + (532.4 - 0.04) / 10.00004)


def test_cubic_step_occurs_once_per_advancing_ack_not_per_segment():
    short = TCPCubic(mss=1000, cwnd=10000, ssthresh=2000)
    cumulative = TCPCubic(mss=1000, cwnd=10000, ssthresh=2000)
    short.ack_received(rtt=0.1, acknowledged_bytes=123)
    cumulative.ack_received(rtt=0.1, acknowledged_bytes=3000)
    assert short.cwnd == cumulative.cwnd == pytest.approx(10000.04)


def test_smoothed_rtt_changes_the_lookahead_not_the_minimum_rtt():
    cubic = TCPCubic(mss=1000, cwnd=10000, ssthresh=2000)
    cubic.ack_received(rtt=0.1, current_time=0)
    cubic.ack_received(rtt=0.9, current_time=1)
    assert cubic.srtt == pytest.approx(0.2)  # (7*0.1+0.9)/8 seconds.
    assert cubic.cwnd == pytest.approx(10000.04 + (691.2 - 0.04) / 10.00004)


def test_missing_rtt_sample_preserves_srtt_but_true_zero_updates_it():
    cubic = TCPCubic(mss=1000)
    cubic.ack_received(rtt=0.2)
    cubic.ack_received(rtt=None)
    assert cubic.srtt == pytest.approx(0.2)
    cubic.ack_received(rtt=0)
    assert cubic.srtt == pytest.approx((7 * 0.2 + 1e-9) / 8, rel=1e-12)


def test_explicit_beta_keeps_its_documented_fraction_of_flight():
    cubic = TCPCubic(mss=1000, cwnd=20000, beta=0.5)
    cubic.set_before_control(1, 10000)
    cubic.consecutive_dupacks_received()
    assert cubic.cwnd == cubic.ssthresh == 5000
    assert cubic.K == pytest.approx(math.cbrt(25))


def test_friendly_region_uses_elapsed_time_and_smoothed_rtt():
    cubic = TCPCubic(mss=1000, cwnd=10000, ssthresh=2000)
    cubic.set_before_control(2, 10000)
    cubic.consecutive_dupacks_received()
    cubic.dupack_over()
    cubic.ack_received(rtt=0.1, current_time=2.1)
    # beta*Wmax + 3*(1-beta)/(1+beta)*t/RTT = 7 + 9/17.
    assert cubic.cwnd == pytest.approx((7 + 9 / 17) * 1000)
    assert cubic.epoch_start == 2


def test_later_loss_tracks_both_maxima_and_uses_actual_flight():
    cubic = TCPCubic(mss=1000, cwnd=30000, ssthresh=2000)
    cubic.set_before_control(1, 30000)
    cubic.consecutive_dupacks_received()
    cubic.dupack_over()
    cubic.cwnd = 20000
    cubic.set_before_control(4, 10000)
    cubic.consecutive_dupacks_received()
    assert cubic.W_last_max == 20
    assert cubic.W_max == 17  # 20*(1+0.7)/2, independently of reduced flight.
    assert cubic.K == pytest.approx(math.cbrt(12.75))
    assert cubic.epoch_start == 4
    assert cubic.ssthresh == cubic.cwnd == 7000


def test_disabling_fast_convergence_preserves_the_observed_maximum():
    cubic = TCPCubic(mss=1000, cwnd=20000, ssthresh=2000)
    cubic.W_last_max = 30
    cubic.fast_convergence = False
    cubic.consecutive_dupacks_received()
    assert cubic.W_max == cubic.W_last_max == 20


def test_cubic_ack_can_step_down_toward_its_target():
    cubic = TCPCubic(mss=1000, cwnd=20000, ssthresh=2000)
    cubic.W_last_max = 30
    cubic.set_before_control(2, 20000)
    cubic.consecutive_dupacks_received()
    cubic.dupack_over()
    cubic.tcp_friendliness = False
    cubic.ack_received(rtt=0.1, current_time=2)
    # Fast convergence makes Wmax=17; its curve begins at 11.9, below cwnd=14.
    target = 17 + 0.4 * (0.1 - math.cbrt(12.75)) ** 3
    assert cubic.cwnd == pytest.approx((14 + (target - 14) / 14) * 1000)
    assert cubic.cwnd < cubic.ssthresh
    # Falling below ssthresh during avoidance must not re-enter slow start.
    window = cubic.cwnd
    cubic.ack_received(rtt=0.1, current_time=2)
    assert cubic.cwnd < window


def test_partial_recovery_ack_holds_window_and_extra_dupacks_inflate():
    cubic = TCPCubic(mss=1000, cwnd=20000)
    cubic.set_before_control(2, 10000)
    cubic.consecutive_dupacks_received()
    cubic.more_dupacks_received()
    assert cubic.cwnd == 8000
    cubic.partial_ack_received(123, 2.1)
    assert cubic.cwnd == 8000
    cubic.dupack_over()
    assert cubic.cwnd == 7000
    assert cubic.epoch_start == 2


def test_tiny_flight_keeps_distinct_recovery_window_and_threshold_floors():
    cubic = TCPCubic(mss=1000, cwnd=20000)
    cubic.set_before_control(1, 123)
    cubic.consecutive_dupacks_received()
    assert cubic.cwnd == 1000
    assert cubic.ssthresh == 2000
    cubic.dupack_over()
    assert cubic.cwnd == 2000


def test_timeout_forgets_maxima_but_preserves_srtt():
    cubic = TCPCubic(mss=1000, cwnd=20000, ssthresh=2000)
    cubic.ack_received(rtt=0.1)
    cubic.set_before_control(2, 10000)
    cubic.timer_expired()
    assert cubic.cwnd == 1000
    assert cubic.ssthresh == 7000
    assert cubic.W_max == cubic.W_last_max == 0
    assert cubic.epoch_start is None
    assert cubic.K == 0
    assert cubic.srtt == pytest.approx(0.1)


def test_finite_flow_with_data_loss_delivers_short_final_segment_once():
    env = simpy.Environment()
    flow = Flow(fid=8, src="src", dst="dst", size=8123, finish_time=5)
    cubic = TCPCubic(mss=1000, cwnd=4000, ssthresh=4000)
    sender = TCPPacketGenerator(env, flow, cubic)
    receiver = TCPSink(env)
    down = Wire(env, lambda: 0.01)
    up = Wire(env, lambda: 0.01)
    attempts = []

    class DropFirstSegment:
        def put(self, packet):
            attempts.append((packet.packet_id, packet.size))
            if len(attempts) == 1:
                return
            down.put(packet)

    sender.out = DropFirstSegment()
    down.out = receiver
    receiver.out = up
    up.out = sender
    env.run(until=5)
    assert sender.last_ack == receiver.bytes_delivered == 8123
    assert attempts.count((0, 1000)) == 2
    assert any(size == 123 for _, size in attempts)
    assert not sender.segment_state
    env.run(until=10)
    assert sender.last_ack == receiver.bytes_delivered == 8123
