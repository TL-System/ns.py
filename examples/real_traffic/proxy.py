"""
A basic example that connects two packet generators to a network wire with
a propagation delay distribution, and then to a packet sink.
"""

import argparse

import simpy

from ns.packet.proxy_generator import ProxyPacketGenerator
from ns.packet.proxy_sink import ProxySink
from ns.port.wire import Wire


def delay_dist():
    """Network wires experience a constant propagation delay of 0.1 seconds."""
    return 0.1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "listen_port", help="The port this process will listen on.", type=int
    )
    parser.add_argument("server_host", help="The remote host to connect to.")
    parser.add_argument("server_port", help="The remote port to connect to.", type=int)
    parser.add_argument("protocol", help="'tcp' or 'udp'", type=str)
    args = parser.parse_args()
    env = simpy.Environment()

    wire1_downstream = Wire(env, delay_dist)
    wire2_upstream = Wire(env, delay_dist)
    client = ProxyPacketGenerator(
        env,
        "ProxyPacketGenerator",
        packet_size=40960,
        listen_port=int(args.listen_port),
        protocol=str(args.protocol),
        debug=False,
    )
    server = ProxySink(
        env,
        "ProxySink",
        packet_size=40960,
        destination=(args.server_host, int(args.server_port)),
        protocol=str(args.protocol),
        debug=False,
    )

    client.out = wire1_downstream
    wire1_downstream.out = server
    server.out = wire2_upstream
    wire2_upstream.out = client

    env.run(until=1000)
