"""
This example shows how to construct a two-level topology consisting of Static Priority
(SP) servers. It also shows how to use strings for flow IDs and to use dictionaries
to provide per-flow weights to DRR servers, so that group IDs and per-group flow IDs can
be easily used to construct globally unique flow IDs.
"""
import simpy

from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.port.port import Port
from ns.scheduler.sp import SPServer


def packet_arrival():
    return 1


def const_size():
    return 1000.0


env = simpy.Environment()

total_groups = 2
total_flows_per_group = 3
source_rate = 8.0 * const_size() / packet_arrival()
service_rate_L1 = 2 * total_groups * total_flows_per_group * source_rate
service_rate_L2 = 2 * total_flows_per_group * source_rate

group_weights = {}
drr_server_per_group = {}

for grp_id in range(total_groups):
    for flow_id in range(total_flows_per_group):
        group_weights[f'grp_{grp_id}_flow_{flow_id}'] = (grp_id +
                                                         1) * 3 + flow_id * 2

ps = PacketSink(env)
drr_server = SPServer(env,
                      service_rate_L1,
                      group_weights,
                      zero_buffer=True,
                      debug=False)
drr_server.out = ps

# Setting up the DRR server for each group
for grp_id in range(total_groups):
    flow_weights = {}
    for flow_id in range(total_flows_per_group):
        flow_weights[f'grp_{grp_id}_flow_{flow_id}'] = (grp_id +
                                                        1) * 3 + flow_id * 2

    drr_server_per_group[f'grp_{grp_id}'] = SPServer(
        env,
        service_rate_L2,
        flow_weights,
        zero_buffer=True,
        zero_downstream_buffer=True,
        debug=True)

    for flow_id in range(total_flows_per_group):
        pg = DistPacketGenerator(env,
                                 f"grp_{grp_id}_flow_{flow_id}",
                                 packet_arrival,
                                 const_size,
                                 initial_delay=0.0,
                                 finish=3,
                                 flow_id=f"grp_{grp_id}_flow_{flow_id}",
                                 debug=True)
        tail_drop_buffer = Port(env,
                                source_rate,
                                qlimit=None,
                                zero_downstream_buffer=True,
                                debug=True)

        pg.out = tail_drop_buffer
        tail_drop_buffer.out = drr_server_per_group[f'grp_{grp_id}']
        drr_server_per_group[f'grp_{grp_id}'].out = drr_server

env.run(until=100)

for grp_id in range(total_groups):
    for flow_id in range(total_flows_per_group):
        print(
            f"At the packet sink, packet arrival times for group {grp_id} and flow {flow_id} are:"
        )
        print(ps.arrivals[f'grp_{grp_id}_flow_{flow_id}'])
