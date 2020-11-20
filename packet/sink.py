"""
Packet sinks record arrival time information from packets. This can take the form of raw arrival times or
inter-arrival times. In addition, the packet sink can record packet waiting times. Supports the `put()`
operation.
"""
import simpy

class PacketSink:
    """ Receives packets and collects delay information into the
        waits list. You can then use this list to look at delay statistics.

        Parameters
        ----------
        env: simpy.Environment
            the simulation environment
        debug: boolean
            if true, the contents of each packet will be printed as it is received.
        rec_arrivals: boolean
            if true, arrivals will be recorded
        absolute_arrivals: boolean
            if true absolute arrival times will be recorded, otherwise the time between
            consecutive arrivals is recorded.
        rec_wait: boolean
            if true waiting time experienced by each packet is recorded
        selector: a function that takes a packet and returns a boolean
            used for selective statistics. Default none.
    """
    def __init__(self, env, rec_arrivals=False, absolute_arrivals=False, rec_waits=True,
                 debug=False, selector=None):
        self.store = simpy.Store(env)
        self.env = env
        self.rec_waits = rec_waits
        self.rec_arrivals = rec_arrivals
        self.absolute_arrivals = absolute_arrivals
        self.waits = []
        self.arrivals = []
        self.debug = debug
        self.packets_rec = 0
        self.bytes_rec = 0
        self.selector = selector
        self.last_arrival = 0.0


    def put(self, pkt):
        if not self.selector or self.selector(pkt):
            now = self.env.now
            if self.rec_waits:
                self.waits.append(self.env.now - pkt.time)
            if self.rec_arrivals:
                if self.absolute_arrivals:
                    self.arrivals.append(now)
                else:
                    self.arrivals.append(now - self.last_arrival)
                self.last_arrival = now
            self.packets_rec += 1
            self.bytes_rec += pkt.size
            if self.debug:
                print(pkt)
