""" 
Implements a packet switch with FIFO or WFQ bounded buffers for outgoing ports.
"""

from ns.port.port import Port
from ns.demux.fib_demux import FIBDemux
from ns.scheduler.wfq import WFQServer


class SimplePacketSwitch:
    """ Implements a simple packet switch with FIFO bounded buffers for outgoing ports.

        Parameters
        ----------
        env: simpy.Environment
            the simulation environment
        nports: int
            the total number of ports on this switch.
        port_rate: float
            the bit rate of the port
        buffer_size: int
            the size of an outgoing port' buffer
        debug: bool
            If True, prints more verbose debug information.
    """
    def __init__(self,
                 env,
                 nports: int,
                 port_rate: float,
                 buffer_size: int,
                 debug: bool = False) -> None:
        self.env = env
        self.ports = []
        for __ in range(nports):
            self.ports.append(
                Port(env,
                     rate=port_rate,
                     qlimit=buffer_size,
                     limit_bytes=False,
                     debug=debug))
        self.demux = FIBDemux(fib=None, outs=self.ports, default=None)

    def put(self, packet):
        """ Sends a packet to this element. """
        self.demux.put(packet)


class WFQPacketSwitch:
    """ Implements a simple packet switch with WFQ bounded buffers for outgoing ports.

        Parameters
        ----------
        env: simpy.Environment
            the simulation environment
        nports: int
            the total number of ports on this switch.
        port_rate: float
            the bit rate of the port
        buffer_size: int
            the size of an outgoing port' buffer
        debug: bool
            If True, prints more verbose debug information.
    """
    def __init__(self, env, nports: int, port_rate: float, buffer: int,
                 weights: list) -> None:
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

    def put(self, packet):
        """ Sends a packet to this element. """
        self.demux.put(packet)
