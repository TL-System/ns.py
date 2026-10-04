import math

from ns.flow.cc import TCPReno
from ns.flow.cubic import TCPCubic


def test_tcp_reno_slow_start_and_avoidance():
    reno = TCPReno(mss=1000, cwnd=1000, ssthresh=8000)

    reno.ack_received()
    assert reno.cwnd == 2000  # slow start adds one MSS per ACK

    reno.cwnd = reno.ssthresh
    reno.ack_received()
    assert reno.cwnd == 8000  # avoidance waits for a window of ACKed bytes
    for _ in range(7):
        reno.ack_received()
    assert reno.cwnd == 9000


def test_tcp_reno_fast_recovery_paths():
    reno = TCPReno(mss=1000, cwnd=16000, ssthresh=16000)

    reno.consecutive_dupacks_received()
    assert reno.ssthresh == 16000 * 0.5
    assert reno.cwnd == reno.ssthresh + 3 * reno.mss

    reno.more_dupacks_received()
    assert reno.cwnd == reno.ssthresh + 4 * reno.mss

    reno.dupack_over()
    assert reno.cwnd == reno.ssthresh


def test_cubic_fast_convergence_tracks_curve_and_observed_maxima():
    cubic = TCPCubic(mss=1000, cwnd=20000, ssthresh=1000)
    cubic.W_last_max = 30  # packets

    cubic.consecutive_dupacks_received()

    # beta=0.7 is the retained window fraction in the Days CUBIC model.
    assert cubic.ssthresh == 14000
    # Fast convergence reduces the curve's W_max; W_last_max records observed cwnd.
    expected_w_max = (1 + cubic.beta) / 2 * (20000 / 1000)
    assert math.isclose(cubic.W_max, expected_w_max)
    assert cubic.W_last_max == 20


def test_cubic_timeout_resets_epoch_and_previous_max():
    cubic = TCPCubic(mss=1000, cwnd=20000, ssthresh=1000)

    cubic.timer_expired()

    assert cubic.cwnd == cubic.mss
    assert cubic.ssthresh == 14000
    assert cubic.W_last_max == 0
    assert cubic.epoch_start is None


def test_cubic_ack_growth_increases_cwnd_in_avoidance():
    cubic = TCPCubic(mss=1000, cwnd=12000, ssthresh=2000)
    window_before = cubic.cwnd
    for i in range(100):
        cubic.ack_received(rtt=0.01, current_time=0.002 * i)

    assert cubic.cwnd > window_before
