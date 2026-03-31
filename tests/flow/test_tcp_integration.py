import pytest

from ns.flow.cc import TCPReno
from ns.flow.flow import Flow
from ns.packet.tcp_generator import TCPPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.port.wire import Wire

simpy = pytest.importorskip("simpy")


def const_delay(value):
    return lambda: value


class DropFirstTransmission:
    def __init__(self, packet_id):
        self.packet_id = packet_id
        self.out = None
        self.dropped = False

    def put(self, packet):
        if packet.packet_id == self.packet_id and not self.dropped:
            self.dropped = True
            return

        self.out.put(packet)


def test_tcp_end_to_end_retransmit_latency_uses_first_transmit_time():
    env = simpy.Environment()
    flow = Flow(fid=7, src="src", dst="dst", size=512, finish_time=5)
    sender = TCPPacketGenerator(
        env,
        flow=flow,
        cc=TCPReno(),
        element_id="tcp-flow",
        debug=False,
    )
    receiver = TCPSink(env, rec_waits=True, debug=False)
    down = Wire(env, const_delay(0.1))
    up = Wire(env, const_delay(0.1))
    drop_first = DropFirstTransmission(packet_id=0)

    sender.out = down
    down.out = drop_first
    drop_first.out = receiver
    receiver.out = up
    up.out = sender

    env.run(until=2.0)

    assert receiver.packet_times[flow.fid] == [0.0]
    assert receiver.waits[flow.fid] == [pytest.approx(1.1)]
    assert sender.last_ack == 512
