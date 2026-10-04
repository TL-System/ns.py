"""Reno feedback traces with byte counts and hand-calculated window decisions."""

import pytest

from ns.flow.cc import CongestionControl, TCPReno


def test_slow_start_short_and_cumulative_acks_stop_at_threshold():
    reno = TCPReno(mss=1000, cwnd=2000, ssthresh=3250)
    windows = []
    for acknowledged in (250, 2000, 1):
        reno.ack_received(acknowledged_bytes=acknowledged)
        windows.append(reno.cwnd)
    # Short ACK: +250; cumulative ACK: at most +MSS; then avoidance
    # starts with fresh credit and cannot grow after only one ACKed byte.
    assert windows == [2250, 3250, 3250]


def test_slow_start_does_not_carry_threshold_overshoot_into_avoidance():
    reno = TCPReno(mss=1000, cwnd=2900, ssthresh=3000)
    reno.ack_received(acknowledged_bytes=1000)
    assert reno.cwnd == 3000
    reno.ack_received(acknowledged_bytes=2999)
    assert reno.cwnd == 3000
    reno.ack_received(acknowledged_bytes=1)
    assert reno.cwnd == 4000


def test_avoidance_requires_a_full_current_window_of_acked_bytes():
    reno = TCPReno(mss=1000, cwnd=4000, ssthresh=4000)
    windows = []
    for acknowledged in (999, 2000, 1000, 1, 4999, 1):
        reno.ack_received(acknowledged_bytes=acknowledged)
        windows.append(reno.cwnd)
    assert windows == [4000, 4000, 4000, 5000, 5000, 6000]


def test_cumulative_avoidance_ack_spends_each_successive_window():
    reno = TCPReno(mss=1000, cwnd=4000, ssthresh=4000)
    # Two complete windows (4000+5000) earn two MSS. The remaining 999
    # bytes belong to the new 6000-byte window rather than the old one.
    reno.ack_received(acknowledged_bytes=9999)
    assert reno.cwnd == 6000
    reno.ack_received(acknowledged_bytes=5001)
    assert reno.cwnd == 7000


def test_direct_ack_calls_default_to_one_mss():
    reno = TCPReno(mss=1000, cwnd=2000, ssthresh=3000)
    reno.ack_received()
    assert reno.cwnd == 3000
    for _ in range(2):
        reno.ack_received()
    assert reno.cwnd == 3000
    reno.ack_received()
    assert reno.cwnd == 4000


def test_legacy_base_adapter_preserves_two_argument_controller_callback():
    class OlderController(CongestionControl):
        def ack_received(self, rtt=0, current_time=0):
            feedback.append((rtt, current_time))

    feedback = []
    cc = OlderController()
    cc.ack_received_bytes(123, None, 1)
    cc.ack_received_bytes(456, 0, 2)
    cc.ack_received_bytes(789, 0.1, 3)
    assert feedback == [(0, 1), (0, 2), (0.1, 3)]


@pytest.mark.parametrize("loss", ["timer_expired", "consecutive_dupacks_received"])
@pytest.mark.parametrize("flight, threshold", [(10000, 5000), (1000, 2000), (0, 2000)])
def test_loss_uses_actual_flight_even_when_window_is_larger(loss, flight, threshold):
    reno = TCPReno(mss=1000, cwnd=30000, ssthresh=30000)
    reno.set_before_control(0.1, flight)
    getattr(reno, loss)()
    assert reno.ssthresh == threshold
    assert reno.cwnd == (1000 if loss == "timer_expired" else threshold + 3000)


@pytest.mark.parametrize("loss", ["timer_expired", "consecutive_dupacks_received"])
def test_direct_loss_without_flight_context_falls_back_to_window(loss):
    reno = TCPReno(mss=1000, cwnd=10000, ssthresh=10000)
    getattr(reno, loss)()
    assert reno.ssthresh == 5000


def test_feedback_context_is_consumed_before_a_later_direct_loss():
    reno = TCPReno(mss=1000, cwnd=10000, ssthresh=10000)
    reno.set_before_control(0.1, 2000)
    reno.ack_received(acknowledged_bytes=1000)
    reno.timer_expired()
    assert reno.ssthresh == 5000


def test_loss_context_is_consumed_before_a_later_direct_loss():
    reno = TCPReno(mss=1000, cwnd=20000, ssthresh=20000)
    reno.set_before_control(0.1, 10000)
    reno.consecutive_dupacks_received()
    assert reno.cwnd == 8000
    reno.timer_expired()
    assert reno.ssthresh == 4000


@pytest.mark.parametrize("loss", ["timer_expired", "consecutive_dupacks_received"])
def test_loss_discards_previous_avoidance_credit(loss):
    reno = TCPReno(mss=1000, cwnd=8000, ssthresh=8000)
    reno.ack_received(acknowledged_bytes=7999)
    reno.set_before_control(0.1, 8000)
    getattr(reno, loss)()
    if loss == "consecutive_dupacks_received":
        reno.dupack_over()
    else:
        for _ in range(3):
            reno.ack_received()
    assert reno.cwnd == 4000
    reno.ack_received(acknowledged_bytes=1)
    assert reno.cwnd == 4000


def test_partial_recovery_deflates_to_threshold_plus_one_segment():
    reno = TCPReno(mss=1000, cwnd=16000, ssthresh=16000)
    reno.set_before_control(0.1, 10000)
    reno.consecutive_dupacks_received()
    reno.more_dupacks_received()
    assert reno.cwnd == 9000
    reno.partial_ack_received(2000, 0.2)
    assert reno.cwnd == 6000
    reno.more_dupacks_received()
    assert reno.cwnd == 7000
    reno.dupack_over()
    assert reno.cwnd == 5000
    reno.ack_received(acknowledged_bytes=4999)
    assert reno.cwnd == 5000
    reno.ack_received(acknowledged_bytes=1)
    assert reno.cwnd == 6000
