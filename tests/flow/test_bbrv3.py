import math

from ns.flow.bbr import BBR, BBRState, ProbeBWPhase
from ns.packet.rate_sample import Connection, RateSample


def make_bbr():
    bbr = BBR(mss=1000, cwnd=12000, rtt_estimate=0.05)
    bbr.rs = RateSample()
    bbr.C = Connection()
    return bbr


def pump_ack(
    bbr: BBR,
    *,
    delivery_rate: float,
    newly_acked: int = None,
    rtt: float = 0.05,
    now: float = 0.0,
):
    newly_acked = newly_acked or bbr.mss
    bbr.rs.delivery_rate = delivery_rate
    bbr.rs.newly_acked = newly_acked
    bbr.rs.interval = max(rtt, 1e-3)
    bbr.rs.rtt = rtt
    bbr.rs.prior_time = now - rtt
    bbr.rs.is_app_limited = False
    bbr.rs.newly_lost = 0
    bbr.rs.prior_delivered = bbr.C.delivered
    bbr.C.delivered += newly_acked
    bbr.set_before_control(now, packet_in_flight=bbr.cwnd)
    bbr.ack_received(rtt, now)


def test_bbr_leaves_startup_after_full_bw():
    bbr = make_bbr()
    now = 0.0
    for _ in range(6):
        pump_ack(bbr, delivery_rate=1_000_000, now=now)
        now += 0.05
    assert bbr.filled_pipe
    assert bbr.state in {BBRState.DRAIN, BBRState.PROBE_BW}


def test_bbr_probe_bw_cycle_covers_all_phases():
    bbr = make_bbr()
    bbr.state = BBRState.PROBE_BW
    bbr.filled_pipe = True
    bbr._reset_probe_bw_cycle()
    now = 0.0
    visited = set()
    for _ in range(8):
        pump_ack(bbr, delivery_rate=1_000_000, now=now)
        visited.add(bbr.probe_phase)
        now += 0.05
    assert ProbeBWPhase.DOWN in visited
    assert ProbeBWPhase.UP in visited


def test_bbr_enters_probe_rtt_when_min_rtt_stale():
    bbr = make_bbr()
    bbr.state = BBRState.PROBE_BW
    bbr.filled_pipe = True
    bbr.min_rtt = 0.05
    bbr.min_rtt_stamp = -BBR.PROBE_RTT_INTERVAL - 1
    pump_ack(bbr, delivery_rate=500_000, now=20.0, rtt=0.05)
    assert bbr.state == BBRState.PROBE_RTT


def test_bbr_limits_cwnd_during_probe_rtt():
    bbr = make_bbr()
    bbr.state = BBRState.PROBE_RTT
    bbr.probe_rtt_start = 0.0
    bbr.min_rtt = 0.05
    bbr.max_bw = 800_000
    bbr.set_before_control(0.1, packet_in_flight=bbr.BBRMinPipeCwnd)
    pump_ack(bbr, delivery_rate=800_000, now=0.1, rtt=0.05)
    assert math.isclose(bbr.cwnd, bbr.BBRMinPipeCwnd, rel_tol=0.01)


def test_startup_counts_rounds_rather_than_ack_packets():
    bbr = make_bbr()
    pump_ack(bbr, delivery_rate=100_000, now=0.1)
    # All these packets were transmitted before the first ACK: one round.
    for i in range(10):
        bbr.rs.prior_delivered = 0
        bbr.rs.newly_acked = 1000
        bbr.rs.delivery_rate = 100_000
        bbr.C.delivered += 1000
        bbr.ack_received(0.05, 0.11 + i * 0.001)
    assert not bbr.filled_pipe
    assert bbr.full_bw_rounds == 0


def test_application_limited_rounds_do_not_end_startup():
    bbr = make_bbr()
    for i in range(8):
        bbr.rs.is_app_limited = True
        bbr.rs.delivery_rate = 10_000
        bbr.rs.interval = 0.05
        bbr.rs.prior_time = 0
        bbr.rs.prior_delivered = bbr.C.delivered
        bbr.rs.newly_acked = 1000
        bbr.C.delivered += 1000
        bbr.ack_received(0.05, i * 0.05)
    assert not bbr.filled_pipe


def test_bandwidth_peak_survives_many_acks_in_same_round():
    bbr = make_bbr()
    pump_ack(bbr, delivery_rate=100_000, now=0.1)
    for i in range(20):
        bbr.rs.prior_delivered = 0
        bbr.rs.delivery_rate = 10_000
        bbr.C.delivered += 1000
        bbr.ack_received(0.05, 0.11 + i * 0.001)
    assert bbr.max_bw == 100_000


def test_lower_application_limited_sample_never_lowers_bandwidth():
    bbr = make_bbr()
    pump_ack(bbr, delivery_rate=100_000, now=0.1)
    bbr.rs.is_app_limited = True
    bbr.rs.delivery_rate = 99_000
    for i in range(20):
        bbr.rs.prior_delivered = bbr.C.delivered
        bbr.C.delivered += 1000
        bbr.ack_received(0.05, 0.2 + i * 0.05)
    assert bbr.max_bw == 100_000


def test_probe_rtt_holds_for_duration_after_drain():
    bbr = make_bbr()
    bbr.min_rtt = 0.05
    bbr.min_rtt_stamp = 0
    pump_ack(bbr, delivery_rate=100_000, now=11)
    assert bbr.state == BBRState.PROBE_RTT
    # The pipe finally drains two seconds after entering: start hold now.
    bbr.set_before_control(13, 4000)
    bbr.ack_received(0.05, 13)
    assert bbr.state == BBRState.PROBE_RTT
    bbr.set_before_control(13.1, 3000)
    bbr.ack_received(0.05, 13.1)
    assert bbr.state == BBRState.PROBE_RTT


def test_probe_rtt_exit_refreshes_expiry():
    bbr = make_bbr()
    bbr.min_rtt = 0.05
    bbr.min_rtt_stamp = 0
    bbr.set_before_control(11, 3000)
    pump_ack(bbr, delivery_rate=100_000, now=11)
    bbr.set_before_control(12, 3000)
    bbr.rs.prior_delivered = bbr.C.delivered
    bbr.C.delivered += 1000
    bbr.ack_received(0.05, 12)
    bbr.set_before_control(12.3, 3000)
    bbr.rs.prior_delivered = bbr.C.delivered
    bbr.C.delivered += 1000
    bbr.ack_received(0.05, 12.3)
    assert bbr.state != BBRState.PROBE_RTT
    bbr.ack_received(0.05, 12.4)
    assert bbr.state != BBRState.PROBE_RTT


def test_timeout_conservation_does_not_exit_on_first_partial_ack():
    bbr = make_bbr()
    bbr.C.delivered = 2000
    bbr.set_before_control(1, 8000)
    bbr.timer_expired()
    bbr.C.delivered = 3000
    bbr.rs.newly_acked = 1000
    bbr.set_before_control(1.1, 7000)
    bbr.ack_received(0, 1.1)
    assert bbr.packet_conservation
    assert bbr.cwnd == 8000
    bbr.C.delivered = 10_000
    bbr.set_before_control(1.2, 0)
    bbr.ack_received(0, 1.2)
    assert not bbr.packet_conservation


def test_invalid_interval_cannot_teach_bandwidth_or_startup():
    bbr = make_bbr()
    bbr.rs.delivery_rate = 100_000
    bbr.rs.interval = 0
    bbr.rs.newly_acked = 1000
    bbr.C.delivered = 1000
    bbr.ack_received(0, 0)
    assert bbr.max_bw == 0
    assert bbr.full_bw == 0


def test_bandwidth_filter_expires_after_ten_delivered_rounds():
    bbr = make_bbr()
    pump_ack(bbr, delivery_rate=100_000, now=0)
    for i in range(1, 10):
        pump_ack(bbr, delivery_rate=10_000, now=i * 0.1)
    assert bbr.max_bw == 100_000
    pump_ack(bbr, delivery_rate=10_000, now=1)
    assert bbr.max_bw == 10_000


def test_app_limited_higher_rate_can_discover_capacity():
    bbr = make_bbr()
    pump_ack(bbr, delivery_rate=100_000, now=0)
    bbr.rs.is_app_limited = True
    bbr.rs.delivery_rate = 200_000
    bbr.C.delivered += 1000
    bbr.ack_received(0.05, 0.1)
    assert bbr.max_bw == 200_000


def test_probe_bw_down_waits_for_drain():
    bbr = make_bbr()
    bbr.state = BBRState.PROBE_BW
    bbr.filled_pipe = True
    pump_ack(bbr, delivery_rate=100_000, now=0)
    assert bbr.probe_phase == ProbeBWPhase.DOWN  # 12000 flight > 5000 BDP.
    bbr.set_before_control(0.1, 4000)
    bbr.rs.prior_delivered = bbr.C.delivered
    bbr.C.delivered += 1000
    bbr.ack_received(0.05, 0.1)
    assert bbr.probe_phase == ProbeBWPhase.CRUISE
    assert bbr.pacing_rate == 100_000


def test_loss_ends_probe_up_before_another_round():
    bbr = make_bbr()
    bbr.state = BBRState.PROBE_BW
    bbr.filled_pipe = True
    bbr.probe_cycle_index = 3
    bbr.probe_phase = ProbeBWPhase.UP
    bbr.cycle_start_time = 1
    bbr.rs.prior_time = 0
    bbr.next_round_delivered = 10_000
    bbr.rs.prior_delivered = 0
    bbr.rs.newly_lost = 1000
    bbr.ack_received(None, 1.001)
    assert bbr.probe_phase == ProbeBWPhase.DOWN


def test_unknown_rtt_does_not_replace_propagation_estimate_with_zero():
    bbr = make_bbr()
    pump_ack(bbr, delivery_rate=100_000, now=0.1)
    bbr.rs.rtt = -1
    bbr.ack_received(0, 0.2)
    assert bbr.min_rtt == 0.05
    bbr.rs.rtt = 0
    bbr.ack_received(0, 0.3)
    assert bbr.min_rtt == 0
