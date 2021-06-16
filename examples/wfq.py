"""
An example of using the WFQ/virtual clock scheduler.

We base our parameter explorations on the first source. We set the output rate of the
WFQ/virtual clock "switch port" at a multiple of the first sources rate.
We also set the "vtick" parameters to the virtual clock switch port relative to this rate.
"""
import simpy
import matplotlib.pyplot as plt

from ns.packet.generator import PacketGenerator
from ns.packet.sink import PacketSink
from ns.demux.flow_demux import FlowDemux
from ns.utils.components import SnoopSplitter
from ns.scheduler.wfq import WFQServer
from ns.scheduler.virtual_clock import VirtualClockServer

if __name__ == '__main__':

    def const_arrival():
        return 1.25

    def const_arrival2():
        return 1.25

    def const_size():
        return 100.0

    env = simpy.Environment()
    pg = PacketGenerator(env,
                         "pg",
                         const_arrival,
                         const_size,
                         initial_delay=0.0,
                         finish=35,
                         flow_id=0)
    pg2 = PacketGenerator(env,
                          "pg2",
                          const_arrival2,
                          const_size,
                          initial_delay=20.0,
                          finish=35,
                          flow_id=1)
    ps = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)
    ps2 = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)
    ps_snoop1 = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)
    ps_snoop2 = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)

    # Set up a WFQ switch port
    source_rate = 8.0 * const_size() / const_arrival()
    phi_base = source_rate
    switch_port = WFQServer(env, source_rate, [0.5 * phi_base, 0.5 * phi_base])
    switch_port2 = VirtualClockServer(env, source_rate,
                                      [2.0 / phi_base, 2.0 / phi_base])
    demux = FlowDemux()
    snoop1 = SnoopSplitter()
    snoop2 = SnoopSplitter()
    pg.out = snoop1
    pg2.out = snoop2
    snoop1.out2 = ps_snoop1
    snoop2.out2 = ps_snoop2

    scheduler_type = "WFQ"
    snoop1.out1 = switch_port
    snoop2.out1 = switch_port
    switch_port.out = demux

    demux.outs = [ps, ps2]
    env.run(until=10000)
    print(ps.arrivals)

    fig, (ax1, ax2) = plt.subplots(nrows=2, sharex=True)
    ax1.vlines(ps_snoop1.arrivals,
               0.0,
               1.0,
               colors="g",
               linewidth=2.0,
               label='flow 0')
    ax1.vlines(ps_snoop2.arrivals,
               0.0,
               0.7,
               colors="r",
               linewidth=2.0,
               label='flow 1')
    ax1.set_title("Arrival times at {} switch".format(scheduler_type))
    ax1.set_xlabel("time")
    ax1.set_ylim([0, 1.5])
    ax1.set_xlim([0, max(ps.arrivals) + 10])
    ax1.legend()
    ax2.vlines(ps.arrivals,
               0.0,
               1.0,
               colors="g",
               linewidth=2.0,
               label='flow 0')
    ax2.vlines(ps2.arrivals,
               0.0,
               0.7,
               colors="r",
               linewidth=2.0,
               label='flow 1')
    ax2.set_title("Departure times from {} switch".format(scheduler_type))
    ax2.set_xlabel("time")
    ax2.set_ylim([0, 1.5])
    ax2.set_xlim([0, max(ps.arrivals) + 10])
    ax2.legend()
    plt.show()
