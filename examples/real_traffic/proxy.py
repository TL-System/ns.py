"""
A basic example that connects two packet generators to a network wire with
a propagation delay distribution, and then to a packet sink.
"""

import simpy
import argparse

from ns.packet.proxy_generator import ProxyPacketGenerator
from ns.packet.proxy_sink import ProxySink

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("listen_port",
                        help="The port this process will listen on.",
                        type=int)
    parser.add_argument("server_host", help="The remote host to connect to.")
    parser.add_argument("server_port",
                        help="The remote port to connect to.",
                        type=int)
    args = parser.parse_args()
    env = simpy.Environment()

    ps = ProxySink(env, rec_flow_ids=False, debug=True)

    pg = ProxyPacketGenerator(env,
                              "flow_1",
                              destination=(args.server_host,
                                           int(args.server_port)),
                              listen_port=int(args.listen_port))

    pg.out = ps

    env.run(until=1000)

    print("Flow 1 packet delays: " +
          ", ".join(["{:.2f}".format(x) for x in ps.waits['flow_1']]))
    print("Flow 2 packet delays: " +
          ", ".join(["{:.2f}".format(x) for x in ps.waits['flow_2']]))

    print("Packet arrival times in flow 1: " +
          ", ".join(["{:.2f}".format(x) for x in ps.arrivals['flow_1']]))

    print("Packet arrival times in flow 2: " +
          ", ".join(["{:.2f}".format(x) for x in ps.arrivals['flow_2']]))
