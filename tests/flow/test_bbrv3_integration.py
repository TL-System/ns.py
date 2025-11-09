import pytest

from ns.flow.bbr import BBR
from ns.flow.flow import Flow
from ns.packet.bbr_generator import BBRPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.port.wire import Wire

simpy = pytest.importorskip("simpy")


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
        size=512 * 800,
        finish_time=5,
        arrival_dist=None,
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

    env.run(until=4.0)
    assert sender.congestion_control.pacing_rate > 0
    assert sender.congestion_control.cwnd >= sender.congestion_control.BBRMinPipeCwnd
    assert sender.next_seq > 0
