"""
A experiment on V. Arun, M. Alizadeh, H. Balakrishnan, "Starvation in
End-to-End Congestion Control," SIGCOMM 2022, Amsterdam, Netherland
"""
import simpy

from ns.demux.flow_demux import FlowDemux
from ns.flow.bbr import BBR
from ns.flow.flow import AppType, Flow
from ns.packet.tcp_generator import TCPPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.port.wire import Wire
from ns.utils.delayer import Delayer, StackDelayer


def packet_arrival():
    """Packets arrive with a constant interval of 0.1 seconds."""
    return 0.01


def packet_size():
    """The packets have a constant size of 1024 bytes."""
    return 512


def zero_delay():
    """Network wires that experience a constant propagation delay of 0 seconds."""
    return 0


def const_delay():
    """Network wires that experience a constant propagation delay of 0.1 seconds."""
    return 0.1


env = simpy.Environment()

flow_1 = Flow(
    fid=0,
    src="flow 1",
    dst="flow 1",
    finish_time=1000,
    typ=AppType.FILE_DOWNLD,
    size=512000 * 2,
    arrival_dist=packet_arrival,
    start_time=0.01,
    size_dist=packet_size,
)

flow_2 = Flow(
    fid=1,
    src="flow 2",
    dst="flow 2",
    typ=AppType.FILE_DOWNLD,
    finish_time=1000,
    size=512000,
    arrival_dist=packet_arrival,
    start_time=20.01,
    size_dist=packet_size,
)

sender_1 = TCPPacketGenerator(
    env,
    element_id=1,
    flow=flow_1,
    cc=BBR(rtt_estimate=0.15),
    rtt_estimate=0.15,
    debug=True,
)

sender_2 = TCPPacketGenerator(
    env,
    element_id=2,
    flow=flow_2,
    cc=BBR(rtt_estimate=0.15),
    rtt_estimate=0.15,
    debug=True,
)

wire_1 = Wire(env, zero_delay)
wire_2 = Wire(env, zero_delay)
wire_4 = Wire(env, const_delay)
wire_5 = Wire(env, const_delay)

pool = StackDelayer(env, speed=12000)
demux = FlowDemux([wire_4, wire_5])

delayer_1 = Delayer(env, 0)
delayer_2 = Delayer(env, 0.4)

receiver_1 = TCPSink(env, rec_waits=True, debug=True, element_id=1)
receiver_2 = TCPSink(env, rec_waits=True, debug=True, element_id=2)

sender_1.out = wire_1
sender_2.out = wire_2
wire_1.out = pool
wire_2.out = pool
pool.out = demux
wire_4.out = receiver_1
wire_5.out = receiver_2
receiver_1.out = delayer_1
receiver_2.out = delayer_2
delayer_1.out = sender_1
delayer_2.out = sender_2

env.run(until=1000)
