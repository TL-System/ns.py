"""
An very simple example of using the test the packet drop in FairPacketSwitch.
It shows a bug in packet dropping process.
"""
import simpy
from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.switch.switch import FairPacketSwitch


def packet_arrival():
    """Constant packet arrival interval."""
    return 1.0


def const_size():
    """Constant packet size in bytes."""
    return 1000.0


env = simpy.Environment()
pg1 = DistPacketGenerator(
    env, "flow_0", packet_arrival, const_size, initial_delay=0.0, finish=1, flow_id=0
)
pg2 = DistPacketGenerator(
    env, "flow_1", packet_arrival, const_size, initial_delay=0.1, finish=1, flow_id=1
)
ps = PacketSink(env)

port_rate = 8000.0  # in bits
buffer_size = 1100  # in bytes

switch = FairPacketSwitch(
    env,
    nports=1,
    port_rate=port_rate,
    buffer_size=buffer_size,
    weights=[1, 2],
    server="DRR",
    debug=True,
)
switch.egress_ports[0].limit_bytes = True
pg1.out = switch
pg2.out = switch
switch.demux.fib = {0: 0, 1: 0}
switch.ports[0].out = ps

env.run()

print("\n==========Basic Info==========")

print(
    f"The buffer size is {buffer_size} bytes, the port rate is {port_rate / 8} bytes/sec, "
    f"and the packet size is {const_size()} bytes."
)

print("==========Result==========")
print("For the switch, the packet arrival times for flow 0 are:")
print(ps.packet_times[0])

print("For the switch, the packet arrival times for flow 1 are:")
print(ps.packet_times[1])

print("At the packet sink, packet arrival times for flow 0 are:")
print(ps.arrivals[0])

print("At the packet sink, packet arrival times for flow 1 are:")
print(ps.arrivals[1])
