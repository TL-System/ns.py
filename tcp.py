"""
A basic example that showcases how TCP can be used to generate packets, and how a TCP sink
can send acknowledgment packets back to the sender in a simple two-hop network.
"""
import simpy
from ns.packet.tcp_generator import TCPPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.port.wire import Wire
from ns.switch.switch import SimplePacketSwitch
from ns.flow.flow import Flow
from ns.flow.bbr import TCPBbr
from ns.flow.cubic import TCPCubic as Cubic
import matplotlib.pyplot as plt


def packet_arrival():
    """ Packets arrive with a constant interval of 0.1 seconds. """
    return 0.1


def packet_size():
    """ The packets have a constant size of 1024 bytes. """
    return 512


def delay_dist():
    """ Network wires experience a constant propagation delay of 0.1 seconds. """
    return 0.1

def long_dist():
    return 0.1

env = simpy.Environment()

flow1 = Flow(fid=0,
            src='flow 1',
            dst='flow 1',
            finish_time=50,
            arrival_dist=packet_arrival,
            size_dist=packet_size)

flow2 = Flow(fid=1,
            src='flow 2',
            dst='flow 2',
            finish_time=50,
            arrival_dist=packet_arrival,
            size_dist=packet_size)

sender1 = TCPPacketGenerator(env,
                            element_id=1,
                            flow=flow1,
                            cc=TCPBbr(rtt_estimate=0.8),
                            # cc=Cubic(),
                            rtt_estimate=0.8,
                            debug=True)

sender2 = TCPPacketGenerator(env,
                            element_id=2,
                            flow=flow2,
                            cc=TCPBbr(rtt_estimate=0.8),
                            # cc=Cubic(),
                            rtt_estimate=0.8,
                            debug=True)


wire1_downstream = Wire(env, delay_dist)
wire1_upstream = Wire(env, delay_dist)
wire2_downstream = Wire(env, delay_dist)
wire2_upstream = Wire(env, delay_dist)

wire3_downstream = Wire(env, delay_dist)
wire3_upstream = Wire(env, delay_dist)
wire4_downstream = Wire(env, delay_dist)
wire4_upstream = Wire(env, delay_dist)
wire5_downstream = Wire(env, long_dist)
wire5_upstream = Wire(env, long_dist)

switch1 = SimplePacketSwitch(
    env,
    nports=3,
    port_rate=16384,  # in bits/second
    buffer_size=5,  # in packets
    debug=True)

switch2 = SimplePacketSwitch(
    env,
    nports=3,
    port_rate=16384,  # in bits/second
    buffer_size=5,  # in packets
    debug=True)

receiver1 = TCPSink(env, rec_waits=True, debug=True, element_id= 1)
receiver2 = TCPSink(env, rec_waits=True, debug=True, element_id= 2)

sender1.out = wire1_downstream
sender2.out = wire2_downstream
wire1_downstream.out = switch1
wire2_downstream.out = switch1
wire3_downstream.out = receiver1
wire4_downstream.out = receiver2
wire5_downstream.out = switch2
receiver1.out = wire3_upstream
receiver2.out = wire4_upstream
wire1_upstream.out = sender1
wire2_upstream.out = sender2
wire3_upstream.out = switch2
wire4_upstream.out = switch2
wire5_upstream.out = switch1

fib1 = {0: 0, 1: 0, 10000: 1, 10001: 2}
switch1.demux.fib = fib1
switch1.demux.outs[0].out = wire5_downstream
switch1.demux.outs[1].out = wire1_upstream
switch1.demux.outs[2].out = wire2_upstream

fib2 = {0: 0, 1: 1, 10000: 2, 10001: 2}  
switch2.demux.fib = fib2
switch2.demux.outs[0].out = wire3_downstream
switch2.demux.outs[1].out = wire4_downstream
switch2.demux.outs[2].out = wire5_upstream

env.run(until=500)

fig, axis = plt.subplots()
print(receiver1.waits[0])
axis.hist(receiver1.waits[0], bins=100)
axis.set_title("Histogram for waiting times #1")
axis.set_xlabel("time")
axis.set_ylabel("normalized frequency of occurrence")
fig.savefig("bbr_WaitHis_1.png")
# plt.show()

fig, axis = plt.subplots()
axis.hist(receiver2.waits[1], bins=100)
print(receiver2.waits[1])
axis.set_title("Histogram for waiting times #2")
axis.set_xlabel("time")
axis.set_ylabel("normalized frequency of occurrence")
fig.savefig("bbr_WaitHis_2.png")
# plt.show()

plt.plot(sender1.cwnd_list)
plt.savefig("bbr_Sender1_cwnd.png")

plt.plot(sender2.cwnd_list)
plt.savefig("bbr_Sender2_cwnd.png")

# fig, axis = plt.subplots()
# axis.hist(receiver1.waits[0], bins=100)
# axis.set_title("Histogram for system occupation times")
# axis.set_xlabel("number")
# axis.set_ylabel("normalized frequency of occurrence")
# fig.savefig("QueueHistogram_1.png")
# plt.show()
# fig, axis = plt.subplots()
# axis.hist(receiver1.arrivals[0], bins=100, density=True)
# axis.set_title("Histogram for sink inter-arrival times")
# axis.set_xlabel("time")
# axis.set_ylabel("normalized frequency of occurrence")
# fig.savefig("ArrivalHistogram_1g").pn
# plt.show()
