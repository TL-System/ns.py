import simpy
import numpy as np
from functools import partial
from random import sample, expovariate

from ns.packet.dist_generator import PacketDistGenerator
from ns.packet.sink import PacketSink
from ns.switch.switch import SimplePacketSwitch
from ns.topos.fattree import build as build_fattree
from ns.topos.utils import generate_fib, generate_flows

if __name__ == "__main__":
    env = simpy.Environment()

    n = 100
    k = 4
    pir = 100000
    buffer_size = 1000
    mean_pkt_size = 100.0

    ft = build_fattree(k)

    hosts = set()
    for n in ft.nodes():
        if ft.nodes[n]['type'] == 'host':
            hosts.add(n)

    all_flows = generate_flows(ft, hosts, n)
    size_dist = partial(expovariate, 1.0 / mean_pkt_size)
    for fid in all_flows:
        arr_dist = partial(expovariate, 1 + np.random.rand())

        pg = PacketDistGenerator(env,
                                 f"Flow_{fid}",
                                 arr_dist,
                                 size_dist,
                                 flow_id=fid)
        ps = PacketSink(env,
                        rec_arrivals=True,
                        absolute_arrivals=True,
                        debug=False)

        all_flows[fid].pkt_gen = pg
        all_flows[fid].pkt_sink = ps

    ft = generate_fib(ft, all_flows)

    for n in ft.nodes():
        node = ft.nodes[n]
        node['device'] = SimplePacketSwitch(env, k, pir, buffer_size)
        node['device'].demux.fib = node['flow_to_port']

    for n in ft.nodes():
        node = ft.nodes[n]
        for port_number, next_hop in node['port_to_nexthop'].items():
            node['device'].ports[port_number].out = ft.nodes[next_hop][
                'device']

    for flow_id, flow in all_flows.items():
        flow.pkt_gen.out = ft.nodes[flow.src]['device']
        ft.nodes[flow.dst]['device'].demux.ends[flow_id] = flow.pkt_sink

    env.run(until=100)

    for flow_id in sample(all_flows.keys(), 5):
        print(f"Flow {flow_id}")
        print(all_flows[flow_id].pkt_sink.waits)
        print(all_flows[flow_id].pkt_sink.arrivals)
