"""
A basic example that showcases how the receiver can send acknowledgment packets
back to the sender in a simple network.
"""
import simpy
from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.port.wire import Wire
from ns.switch.switch import SimplePacketSwitch


def packet_arrival():
    """ Packets arrive with a constant interval of 2 seconds. """
    return 2.0


def delay_dist():
    """ Network wires experience a constant propagation delay of 0.1 seconds. """
    return 0.1


def packet_size():
    """ The packets have a constant size of 100 bytes. """
    return 100


env = simpy.Environment()

sender_ack = PacketSink(env, rec_flow_ids=False)
receiver = PacketSink(env, rec_flow_ids=False)

sender = DistPacketGenerator(env,
                             "flow_1",
                             packet_arrival,
                             packet_size,
                             flow_id=0)

wire1_downstream = Wire(env, delay_dist)
wire1_upstream = Wire(env, delay_dist)
wire2_downstream = Wire(env, delay_dist)
wire2_upstream = Wire(env, delay_dist)

switch = SimplePacketSwitch(
    env,
    nports=2,
    port_rate=800.0,  # in bits/second
    buffer_size=100,  # in bytes
)

sender.out = wire1_downstream
wire1_downstream.out = switch
wire2_downstream.out = receiver
receiver.ack_out = wire2_upstream
wire2_upstream.out = switch

fib = {0: 0, 10000: 1}
switch.demux.fib = fib
switch.demux.outs[0].out = wire2_downstream
switch.demux.outs[1].out = wire1_upstream

wire1_upstream.out = sender_ack

env.run(until=100)

print("Flow 1 arrival delays at the receiver: " +
      ", ".join(["{:.2f}".format(x) for x in receiver.waits['flow_1']]))

print("Flow 1 arrival times at the receiver: " +
      ", ".join(["{:.2f}".format(x) for x in receiver.arrivals['flow_1']]))

print("Flow 1 round-trip times: " +
      ", ".join(["{:.2f}".format(x) for x in sender_ack.waits['flow_1']]))

print("Acknowledgement arrival times in flow 1: " +
      ", ".join(["{:.2f}".format(x) for x in sender_ack.arrivals['flow_1']]))
