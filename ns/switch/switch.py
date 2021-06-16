from ns.port.port import SwitchPort
from ns.demux.fib_demux import FIBDemux
from ns.scheduler.wfq import WFQServer


class SimplePacketSwitch:
    def __init__(self, env, nports, port_rate, buffer, sinks=None) -> None:
        self.env = env
        self.ports = []
        for i in range(nports):
            self.ports.append(
                SwitchPort(env,
                           rate=port_rate,
                           qlimit=buffer,
                           limit_bytes=False,
                           zero_downstream_buffer=False,
                           debug=False))
        self.demux = FIBDemux(env, fib=None, outs=self.ports, default=None)

    def put(self, pkt):
        """ Sends the packet 'pkt' to the next-hop element. """
        self.demux.put(pkt)


class WFQPacketSwitch:
    def __init__(self, env, nports, port_rate, buffer, weights) -> None:
        self.env = env
        self.ports = []
        self.egress_ports = []
        self.schedulers = []
        for i in range(nports):
            swp = SwitchPort(env,
                             rate=port_rate,
                             qlimit=buffer,
                             limit_bytes=False,
                             zero_downstream_buffer=False,
                             debug=False)
            wfqs = WFQServer(env, rate=port_rate, weights=weights)
            swp.out = wfqs
            self.egress_ports.append(swp)
            self.schedulers.append(wfqs)
            self.ports.append(wfqs.out)
        self.demux = FIBDemux(env,
                              fib=None,
                              outs=self.egress_ports,
                              default=None)

    def put(self, pkt):
        """ Sends the packet 'pkt' to the next-hop element. """
        self.demux.put(pkt)
