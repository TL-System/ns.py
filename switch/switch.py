import os,sys

from port.port import SwitchPort
from demux.fib_demux import FIBDemux
from scheduler.wfq import WFQServer

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

class SimplePacketSwitch:
  def __init__(
    self,
    env,
    nports,
    port_rate,
    buffer,
    sinks=None) -> None:
    self.env = env
    self.ports = []
    for i in range(nports):
      self.ports.append(SwitchPort(
        env,
        rate=port_rate,
        qlimit=buffer,
        limit_bytes=False,
        zero_downstream_buffer=False,
        debug=False)
      )
    self.demux = FIBDemux(env, fib=None, outs=self.ports, default=None)
  
  def put(self, pkt):
    self.demux.put(pkt)


class WFQPacketSwitch:
  def __init__(self, env, nports, port_rate, buffer, weights) -> None:
      self.env = env
      self.ports = []
      self.egress_ports = []
      self.schedulers = []
      for i in range(nports):
        swp = SwitchPort(
          env,
          rate=port_rate,
          qlimit=buffer,
          limit_bytes=False,
          zero_downstream_buffer=False,
          debug=False
        )
        wfqs = WFQServer(env, rate=port_rate, weights=weights)
        swp.out = wfqs
        self.egress_ports.append(swp)
        self.schedulers.append(wfqs)
        self.ports.append(wfqs.out)
      self.demux = FIBDemux(env, fib=None, outs=self.egress_ports, default=None)

  def put(self,pkt):
    self.demux.put(pkt)