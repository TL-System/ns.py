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
