"""
Packet sinks record arrival time information from packets. This can take the form of raw arrival times or
inter-arrival times. In addition, the packet sink can record packet waiting times. Supports the `put()`
operation.
"""
import simpy
from collections import defaultdict as dd


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
    def __init__(self,
                 env,
                 rec_arrivals=False,
                 absolute_arrivals=False,
                 rec_waits=True,
                 rec_flow_ids=True,
                 debug=False):
        self.store = simpy.Store(env)
        self.env = env
        self.rec_waits = rec_waits
        self.rec_flow_ids = rec_flow_ids
        self.rec_arrivals = rec_arrivals
        self.absolute_arrivals = absolute_arrivals
        self.waits = dd(list)
        self.arrivals = dd(list)
        self.packets_received = dd(lambda: 0)
        self.bytes_received = dd(lambda: 0)
        self.pktsizes = dd(list)
        self.pkttimes = dd(list)
        self.perhoptimes = dd(list)

        self.first_arrival = dd(lambda: 0)
        self.last_arrival = dd(lambda: 0)
        self.debug = debug

    def put(self, pkt):
        """ Sends the packet 'pkt' to the next-hop element. """
        now = self.env.now

        if self.debug:
            print(f"At packet sink: {pkt}")

        if self.rec_flow_ids:
            rec_index = pkt.flow_id
        else:
            rec_index = pkt.src

        if self.rec_waits:
            self.waits[rec_index].append(self.env.now - pkt.time)
            self.pktsizes[rec_index].append(pkt.size)
            self.pkttimes[rec_index].append(pkt.time)
            self.perhoptimes[rec_index].append(pkt.perhoptime)

        if self.rec_arrivals:
            self.arrivals[rec_index].append(now)
            if len(self.arrivals[rec_index]) == 1:
                self.first_arrival[rec_index] = now

            if not self.absolute_arrivals:
                self.arrivals[rec_index][
                    -1] = now - self.last_arrival[rec_index]

            self.last_arrival[rec_index] = now

        self.packets_received[rec_index] += 1
        self.bytes_received[rec_index] += pkt.size
