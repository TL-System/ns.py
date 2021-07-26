""" 
Implements a packet switch with FIFO or WFQ bounded buffers for outgoing ports.
"""

from ns.port.port import Port
from ns.demux.fib_demux import FIBDemux
from ns.scheduler.wfq import WFQServer
from ns.scheduler.drr import DRRServer
from ns.scheduler.virtual_clock import VirtualClockServer


class SimplePacketSwitch:
    """ Implements a packet switch with a FIFO bounded buffer on each of the outgoing ports.

        Parameters
        ----------
        env: simpy.Environment
            the simulation environment.
        nports: int
            the total number of ports on this switch.
        port_rate: float
            the bit rate of the port.
        buffer_size: int
            the size of an outgoing port' bounded buffer, in packets.
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


class FairPacketSwitch:
    """ Implements a fair packet switch with a choice of a WFQ, Virtual Clock, or DRR
        scheduler, as well as bounded buffers, on each of the outgoing ports.

        Parameters
        ----------
        env: simpy.Environment
            the simulation environment.
        nports: int
            the total number of ports on this switch.
        port_rate: float
            the bit rate of each outgoing port.
        buffer_size: int
            the size of an outgoing port' bounded buffer, in packets.
        weights: list or dict
            This can be either a list or a dictionary. If it is a list, it uses the flow_id
            as its index to look for the flow's corresponding weight. If it is a dictionary,
            it contains (flow_id -> weight) pairs for each possible flow_id.
        type: str (possible values: 'WFQ', 'DRR', or 'VirtualClock')
            The type of the fair scheduler used for each outgoing port.
        debug: bool
            If True, prints more verbose debug information.
    """
    def __init__(self,
                 env,
                 nports: int,
                 port_rate: float,
                 buffer_size: int,
                 weights,
                 server: str,
                 debug: bool = False) -> None:
        self.env = env
        self.ports = []
        self.egress_ports = []

        for __ in range(nports):
            egress_port = Port(env,
                               rate=port_rate,
                               qlimit=buffer_size,
                               limit_bytes=False,
                               zero_downstream_buffer=True,
                               debug=debug)

            scheduler = None
            if server == 'WFQ':
                scheduler = WFQServer(env,
                                      rate=port_rate,
                                      weights=weights,
                                      zero_buffer=True,
                                      debug=debug)
            elif server == 'DRR':
                scheduler = DRRServer(env,
                                      rate=port_rate,
                                      weights=weights,
                                      zero_buffer=True,
                                      debug=debug)
            elif server == 'VirtualClock':
                scheduler = VirtualClockServer(env,
                                               rate=port_rate,
                                               vticks=weights,
                                               zero_buffer=True,
                                               debug=debug)
            else:
                raise ValueError(
                    "Scheduler type must be either 'WFQ', 'DRR', or 'VirtualClock'."
                )

            egress_port.out = scheduler

            self.egress_ports.append(egress_port)
            self.ports.append(scheduler)

        self.demux = FIBDemux(fib=None, outs=self.egress_ports, default=None)

    def put(self, packet):
        """ Sends a packet to this element. """
        self.demux.put(packet)
