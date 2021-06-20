from ns.port.port import Port
from ns.demux.fib_demux import FIBDemux
from ns.scheduler.wfq import WFQServer


class SimplePacketSwitch:
    def __init__(self, env, nports, port_rate, buffer_size) -> None:
        self.env = env
        self.ports = []
        for __ in range(nports):
            self.ports.append(
                Port(env,
                     rate=port_rate,
                     qlimit=buffer_size,
                     limit_bytes=False))
        self.demux = FIBDemux(fib=None, outs=self.ports, default=None)

    def put(self, pkt):
        """ Sends the packet 'pkt' to this element. """
        self.demux.put(pkt)


class WFQPacketSwitch:
    def __init__(self, env, nports, port_rate, buffer, weights) -> None:
        self.env = env
        self.ports = []
        self.egress_ports = []
        self.schedulers = []
        for __ in range(nports):
            swp = Port(env,
                       rate=port_rate,
                       qlimit=buffer,
                       limit_bytes=False,
                       zero_downstream_buffer=True)
            wfqs = WFQServer(env,
                             rate=port_rate,
                             weights=weights,
                             zero_buffer=True)
            swp.out = wfqs
            self.egress_ports.append(swp)
            self.schedulers.append(wfqs)
            self.ports.append(wfqs.out)
        self.demux = FIBDemux(fib=None, outs=self.egress_ports, default=None)

    def put(self, pkt):
        """ Sends the packet 'pkt' to this element. """
        self.demux.put(pkt)
