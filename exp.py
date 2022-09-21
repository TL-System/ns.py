"""
A basic example that showcases how TCP can be used to generate packets, and how a TCP sink
can send acknowledgment packets back to the sender in a simple two-hop network.
"""
import simpy
from ns.packet.tcp_generator import TCPPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.utils.delayer import Delayer, StackDelayer
from ns.port.wire import Wire
from ns.demux.flow_demux import FlowDemux
from ns.flow.flow import Flow, AppType
from ns.flow.bbr import TCPBbr
from ns.flow.cubic import TCPCubic as Cubic
import matplotlib.pyplot as plt


def packet_arrival():
    """ Packets arrive with a constant interval of 0.1 seconds. """
    return 0.01


def packet_size():
    """ The packets have a constant size of 1024 bytes. """
    return 512


def delay_dist():
    """ Network wires experience a constant propagation delay of 0 seconds. """
    return 0

def rm_dist():
    return 0.1


env = simpy.Environment()

flow1 = Flow(fid=0,
            src='flow 1',
            dst='flow 1',
            finish_time=1000,
            typ = AppType.FILE_DOWNLD,
            size = 512000, 
            # arrival_dist=packet_arrival,
            start_time=0.01,
            size_dist=packet_size)

flow2 = Flow(fid=1,
            src='flow 2',
            dst='flow 2',
            typ = AppType.FILE_DOWNLD,
            finish_time=1000,
            size = 512000,
            # arrival_dist=packet_arrival,
            start_time=1000.01,
            size_dist=packet_size)

sender1 = TCPPacketGenerator(env,
                            element_id=1,
                            flow=flow1,
                            cc=TCPBbr(rtt_estimate=0.15),
                            # cc=Cubic(),
                            rtt_estimate=0.15,
                            debug=True)

sender2 = TCPPacketGenerator(env,
                            element_id=2,
                            flow=flow2,
                            cc=TCPBbr(rtt_estimate=0.15),
                            # cc=Cubic(),
                            rtt_estimate=0.15,
                            debug=True)


wire1 = Wire(env, delay_dist)
wire2 = Wire(env, delay_dist)
wire4 = Wire(env, rm_dist)
wire5 = Wire(env, rm_dist)

pool = StackDelayer(env, speed=24000)
demux = FlowDemux([wire4, wire5])

max_delay = 0 #TBA
delayer1 = Delayer(env, max_delay)
delayer2 = Delayer(env, max_delay)

receiver1 = TCPSink(env, rec_waits=True, debug=True, element_id= 1)
receiver2 = TCPSink(env, rec_waits=True, debug=True, element_id= 2)

sender1.out = wire1
sender2.out = wire2
wire1.out = pool
wire2.out = pool
pool.out= demux
wire4.out = receiver1
wire5.out = receiver2
receiver1.out = delayer1
receiver2.out = delayer2
delayer1.out = sender1
delayer2.out = sender2

env.run(until=200)

fig, axis = plt.subplots()
axis.hist(receiver1.waits[0], bins=100)
axis.set_title("Histogram for waiting times #1")
axis.set_xlabel("time")
axis.set_ylabel("normalized frequency of occurrence")
fig.savefig("bbr_WaitHis_1.png")
# plt.show()

fig, axis = plt.subplots()
axis.hist(receiver2.waits[1], bins=100)
axis.set_title("Histogram for waiting times #2")
axis.set_xlabel("time")
axis.set_ylabel("normalized frequency of occurrence")
fig.savefig("bbr_WaitHis_2.png")
# plt.show()

fig, axis = plt.subplots()
axis.hist(receiver1.arrivals[0], bins=100)
axis.set_title("Histogram for arrival times #1")
axis.set_xlabel("time")
axis.set_ylabel("normalized frequency of occurrence")
fig.savefig("bbr_WaitHis_1.png")
# plt.show()

fig, axis = plt.subplots()
axis.hist(receiver2.arrivals[1], bins=100)
axis.set_title("Histogram for arrival times #2")
axis.set_xlabel("time")
axis.set_ylabel("normalized frequency of occurrence")
fig.savefig("bbr_WaitHis_2.png")

plt.plot(sender1.time_list, sender1.rate_sample_list, marker = 'o', # 点的形状
         markersize = 6, # 点的大小
         markeredgecolor='black', # 点的边框色
         markerfacecolor='steelblue' # 点的填充色
)
plt.savefig("bbr_rs.png")