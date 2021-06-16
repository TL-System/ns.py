"""
A PacketSink is designed to record both arrival times and waiting times from the incoming packets. 

By default, it records absolute arrival times, but it can also be initialized to record inter-arrival
times.
"""
from collections import defaultdict as dd

import simpy


class PacketSink:
    """ A PacketSink is designed to record both arrival times and waiting times from the incoming
    packets. By default, it records absolute arrival times, but it can also be initialized to record
    inter-arrival times.

    Parameters
    ----------
    env: simpy.Environment
        the simulation environment
    rec_arrivals: bool
        if true, arrivals will be recorded
    absolute_arrivals: bool
        if true absolute arrival times will be recorded, otherwise the time between
        consecutive arrivals is recorded.
    rec_waits: bool
        if True, the waiting times experienced by the packets are recorded
    rec_flow_ids: bool
        if True, the flow IDs that the packets are used as the index for recording;
        otherwise, the 'src' field in the packets are used
    debug: bool
        if True, the contents of each packet will be printed as it is received.
    """
    def __init__(self,
                 env,
                 rec_arrivals: bool = True,
                 absolute_arrivals: bool = True,
                 rec_waits: bool = True,
                 rec_flow_ids: bool = True,
                 debug: bool = False):
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
        self.packet_sizes = dd(list)
        self.packet_times = dd(list)
        self.perhop_times = dd(list)

        self.first_arrival = dd(lambda: 0)
        self.last_arrival = dd(lambda: 0)
        self.debug = debug

    def put(self, pkt):
        """ Sends the packet 'pkt' to this element. """
        now = self.env.now

        if self.debug:
            print(f"At packet sink: {pkt}")

        if self.rec_flow_ids:
            rec_index = pkt.flow_id
        else:
            rec_index = pkt.src

        if self.rec_waits:
            self.waits[rec_index].append(self.env.now - pkt.time)
            self.packet_sizes[rec_index].append(pkt.size)
            self.packet_times[rec_index].append(pkt.time)
            self.perhop_times[rec_index].append(pkt.perhop_time)

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
