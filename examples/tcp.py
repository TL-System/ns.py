"""
A basic example that showcases how the receiver can send acknowledgment packets
back to the sender in a simple network.
"""
import simpy
from ns.packet.tcp_generator import TCPPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.port.wire import Wire
from ns.switch.switch import SimplePacketSwitch
from ns.flow.flow import Flow
from ns.flow.cubic import TCPCubic


def packet_arrival():
    """ Packets arrive with a constant interval of 2 seconds. """
    return 2.0


def delay_dist():
    """ Network wires experience a constant propagation delay of 0.1 seconds. """
    return 0.1


def packet_size():
    """ The packets have a constant size of 100 bytes. """
    return 20480


env = simpy.Environment()

flow = Flow(fid=0,
            finish_time=30,
            arrival_dist=packet_arrival,
            size_dist=packet_size)

sender = TCPPacketGenerator(env,
                            flow=flow,
                            cc=TCPCubic(),
                            rtt_estimate=0.8,
                            debug=True)

wire1_downstream = Wire(env, delay_dist)
wire1_upstream = Wire(env, delay_dist)
wire2_downstream = Wire(env, delay_dist)
wire2_upstream = Wire(env, delay_dist)

switch = SimplePacketSwitch(
    env,
    nports=2,
    port_rate=8192,  # in bits/second
    buffer_size=1024,  # in bytes
)

receiver = TCPSink(env, rec_flow_ids=False)

sender.out = wire1_downstream
wire1_downstream.out = switch
wire2_downstream.out = receiver
receiver.out = wire2_upstream
wire2_upstream.out = switch

fib = {0: 0, 10000: 1}
switch.demux.fib = fib
switch.demux.outs[0].out = wire2_downstream
switch.demux.outs[1].out = wire1_upstream

wire1_upstream.out = sender

env.run(until=100)
