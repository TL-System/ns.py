import pytest

simpy = pytest.importorskip("simpy")

from ns.flow.bbr import BBR, BBRState
from ns.flow.flow import Flow
from ns.packet.bbr_generator import BBRPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.port.wire import Wire


def const_delay(value):
    return lambda: value


def const_arrival(value):
    return lambda: value


def const_size(value):
    return lambda: value


def test_bbr_end_to_end_reaches_probe_bw():
    env = simpy.Environment()
    flow = Flow(
        fid=42,
        src="src",
        dst="dst",
        size=512 * 400,
        finish_time=5,
        arrival_dist=const_arrival(0.01),
        size_dist=const_size(512),
    )
    cc = BBR(mss=512, cwnd=8192, rtt_estimate=0.02)
    sender = BBRPacketGenerator(
        env,
        flow=flow,
        cc=cc,
        element_id="bbr-flow",
        rtt_estimate=0.02,
        debug=False,
    )
    receiver = TCPSink(env, rec_waits=True, debug=False)
    down = Wire(env, const_delay(0.005))
    up = Wire(env, const_delay(0.005))

    sender.out = down
    down.out = receiver
    receiver.out = up
    up.out = sender

    env.run(until=3.0)
    assert sender.congestion_control.state in {
        BBRState.PROBE_BW,
        BBRState.PROBE_RTT,
    }
    assert sender.congestion_control.pacing_rate > 0
    assert sender.congestion_control.cwnd >= sender.congestion_control.BBRMinPipeCwnd
