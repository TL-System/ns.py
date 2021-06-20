"""
An example of combining a Random Early Detection (RED) port and a WFQ server.

The RED port serves as an upstream buffer, configured to recognize that its downstream
element has a zero-buffer configuration. The WFQ server is initialized with zero buffering
as the downstream element after the RED port. Packets will be dropped when the downstream WFQ
server is the bottleneck.
"""
import simpy

from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.port.red_port import REDPort
from ns.port.port import Port
from ns.scheduler.wfq import WFQServer
from ns.utils.splitter import Splitter


def packet_arrival():
    """Constant packet arrival at one per second."""
    return 1


def packet_size():
    """Constant packet size of 1000 bytes."""
    return 1000


env = simpy.Environment()
pg1 = DistPacketGenerator(env,
                          "flow_1",
                          packet_arrival,
                          packet_size,
                          initial_delay=0.0,
                          finish=100,
                          flow_id=0)
pg2 = DistPacketGenerator(env,
                          "flow_2",
                          packet_arrival,
                          packet_size,
                          initial_delay=0.0,
                          finish=100,
                          flow_id=1)

tail_drop_sink = PacketSink(env)
red_sink = PacketSink(env)

source_rate = 8.0 * packet_size() / packet_arrival()

red_buffer_1 = REDPort(env,
                       source_rate,
                       qlimit=8,
                       max_threshold=6,
                       min_threshold=2,
                       max_probability=0.8,
                       zero_downstream_buffer=True)
red_buffer_2 = REDPort(env,
                       source_rate,
                       qlimit=8,
                       max_threshold=6,
                       min_threshold=2,
                       max_probability=0.8,
                       zero_downstream_buffer=True)

tail_drop_buffer_1 = Port(env,
                          source_rate,
                          qlimit=8,
                          zero_downstream_buffer=True)
tail_drop_buffer_2 = Port(env,
                          source_rate,
                          qlimit=8,
                          zero_downstream_buffer=True)
wfq_server_1 = WFQServer(env,
                         source_rate, [0.5 * source_rate, 0.5 * source_rate],
                         zero_buffer=True)
wfq_server_2 = WFQServer(env,
                         source_rate, [0.5 * source_rate, 0.5 * source_rate],
                         zero_buffer=True)
splitter_1 = Splitter()
splitter_2 = Splitter()

pg1.out = splitter_1
pg2.out = splitter_2

splitter_1.out1 = tail_drop_buffer_1
tail_drop_buffer_1.out = wfq_server_1
splitter_2.out1 = tail_drop_buffer_2
tail_drop_buffer_2.out = wfq_server_1
wfq_server_1.out = tail_drop_sink

splitter_1.out2 = red_buffer_1
red_buffer_1.out = wfq_server_2
splitter_2.out2 = red_buffer_2
red_buffer_2.out = wfq_server_2
wfq_server_2.out = red_sink

env.run(until=10000)

print("The number of packets dropped in tail drop upstream buffers:")
print(f"Flow 0: {tail_drop_buffer_1.packets_dropped}")
print(f"Flow 1: {tail_drop_buffer_2.packets_dropped}")

print("Statistics for packets passing through tail drop upstream buffers: ")

for flow_id in tail_drop_sink.waits.keys():
    print(f"Packet delays in flow {flow_id}: {tail_drop_sink.waits[flow_id]}")
    print(
        f"The number of packets received in flow {flow_id}: {tail_drop_sink.packets_received[flow_id]}"
    )
    print(
        f"The number of bytes received in flow {flow_id}: {tail_drop_sink.bytes_received[flow_id]}"
    )
    print(
        f"The absolute packet arrival times in flow {flow_id}: {tail_drop_sink.arrivals[flow_id]}"
    )

print("The number of packets dropped in RED upstream buffers:")
print(f"Flow 0: {red_buffer_1.packets_dropped}")
print(f"Flow 1: {red_buffer_2.packets_dropped}")

print("Statistics for packets passing through RED upstream buffers: ")
for flow_id in red_sink.waits.keys():
    print(f"Packet delays in flow {flow_id}: {red_sink.waits[flow_id]}")
    print(
        f"The number of packets received in flow {flow_id}: {red_sink.packets_received[flow_id]}"
    )
    print(
        f"The number of bytes received in flow {flow_id}: {red_sink.bytes_received[flow_id]}"
    )
    print(
        f"The absolute packet arrival times in flow {flow_id}: {red_sink.arrivals[flow_id]}"
    )
