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
from ns.flow.cc import TCPReno


def packet_arrival():
    """ Packets arrive with a constant interval of 0.1 seconds. """
    return 0.05


def delay_dist():
    """ Network wires experience a constant propagation delay of 0.1 seconds. """
    return 0.1


def packet_size():
    """ The packets have a constant size of 1024 bytes. """
    return 1024


env = simpy.Environment()

flow = Flow(fid=0,
            src='flow 1',
            finish_time=300,
            arrival_dist=packet_arrival,
            size_dist=packet_size)

sender = TCPPacketGenerator(env,
                            flow=flow,
                            cc=TCPReno(),
                            rtt_estimate=0.5,
                            debug=True)

wire1_downstream = Wire(env, delay_dist)
wire1_upstream = Wire(env, delay_dist)
wire2_downstream = Wire(env, delay_dist)
wire2_upstream = Wire(env, delay_dist)

switch = SimplePacketSwitch(
    env,
    nports=2,
    port_rate=81920,  # in bits/second
    buffer_size=4096,  # in bytes
)

receiver = TCPSink(env, rec_waits=True, debug=True)

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
