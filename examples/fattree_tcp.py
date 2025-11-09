from functools import partial

import simpy

from ns.flow.cc import TCPReno
from ns.packet.tcp_generator import TCPPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.switch.switch import SimplePacketSwitch
from ns.topos.fattree import build as build_fattree
from ns.topos.utils import generate_fib, generate_flows

env = simpy.Environment()

n_flows = 10
finish_time = 10
k = 4
pir = 10000000000  # 10Gbps
buffer_size = 1000


def size_dist():
    return 1024


def arrival_dist():
    return 0.0008  # 10Mbps


ft = build_fattree(k)

hosts = set()
for n in ft.nodes():
    if ft.nodes[n]["type"] == "host":
        hosts.add(n)

all_flows = generate_flows(
    ft,
    hosts,
    n_flows,
    finish_time=finish_time,
    arrival_dist=arrival_dist,
    size_dist=size_dist,
)

for fid in all_flows:
    pg = TCPPacketGenerator(
        env, all_flows[fid], cc=TCPReno(), element_id=fid, debug=False
    )
    ps = TCPSink(env)

    all_flows[fid].pkt_gen = pg
    all_flows[fid].pkt_sink = ps

ft = generate_fib(ft, all_flows, tcp=True)

n_classes_per_port = 4
weights = {c: 1 for c in range(n_classes_per_port)}


def flow_to_classes(packet, n_id=0, fib=None):
    return (packet.flow_id + n_id + fib[packet.flow_id]) % n_classes_per_port


for node_id in ft.nodes():
    node = ft.nodes[node_id]
    flow_classes = partial(flow_to_classes, n_id=node_id, fib=node["flow_to_port"])
    # node["device"] = FairPacketSwitch(
    #     env, k, pir, buffer_size, weights, "DRR", flow_classes, element_id=f"{node_id}"
    # ）
    node["device"] = SimplePacketSwitch(
        env, k, pir, buffer_size, element_id=f"{node_id}"
    )
    node["device"].demux.fib = node["flow_to_port"]

for n in ft.nodes():
    node = ft.nodes[n]
    for port_number, next_hop in node["port_to_nexthop"].items():
        node["device"].ports[port_number].out = ft.nodes[next_hop]["device"]


for flow_id, flow in all_flows.items():
    flow.pkt_gen.out = ft.nodes[flow.src]["device"]
    ft.nodes[flow.dst]["device"].demux.ends[flow_id] = flow.pkt_sink

    flow.pkt_sink.out = ft.nodes[flow.dst]["device"]
    ft.nodes[flow.src]["device"].demux.ends[flow_id + 10000] = flow.pkt_gen


env.run(until=100)

# for flow_id in sample(sorted(all_flows.keys()), 5):
#     print(f"Flow {flow_id}")
#     print(all_flows[flow_id].pkt_sink.waits)
#     print(all_flows[flow_id].pkt_sink.arrivals)
#     print(all_flows[flow_id].pkt_sink.perhop_times)
