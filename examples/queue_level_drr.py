"""
An example of using the Deficit Round Robin (DRR) server.
"""
import simpy

from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.port.port import Port
from ns.scheduler.drr import DRRServer


def packet_arrival():
    return 1.75


def const_size():
    return 1000.0


env = simpy.Environment()

total_groups = 3
total_flows_per_group = 8
source_rate = 8.0 * const_size() / packet_arrival()

pg = {}
group_weights = {}
drr_server_per_group = {}

for grp_id in range(total_groups):
    for flow_id in range(total_flows_per_group):
        group_weights[f'grp_{grp_id}_flow_{flow_id}'] = 1

ps = PacketSink(env)
drr_server = DRRServer(env, source_rate, group_weights, debug=True)
drr_server.out = ps

# Setting up the DRR server for each group
for grp_id in range(total_groups):
    flow_weights = {}
    for flow_id in range(total_flows_per_group):
        flow_weights[f'grp_{grp_id}_flow_{flow_id}'] = 1

    group_weights[f'grp_{grp_id}'] = 1

    drr_server_per_group[f'grp_{grp_id}'] = DRRServer(env,
                                                      source_rate,
                                                      flow_weights,
                                                      zero_buffer=True,
                                                      debug=True)

    for flow_id in range(total_flows_per_group):
        pg = DistPacketGenerator(env,
                                 f"grp_{grp_id}_flow_{flow_id}",
                                 packet_arrival,
                                 const_size,
                                 initial_delay=0.0,
                                 finish=35,
                                 flow_id=f"grp_{grp_id}_flow_{flow_id}")
        tail_drop_buffer = Port(env,
                                source_rate,
                                qlimit=8,
                                zero_downstream_buffer=True)

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
