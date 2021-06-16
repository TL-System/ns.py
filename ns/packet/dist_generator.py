"""
A PacketDistGenerator simulates the sending of packets with a specified inter-arrival time
distribution and a packet size distribution. One can set an initial delay and a finish
time for packet generation. In addition one can set the source id and flow ids for the
packets generated. The PacketDistGenerator's `out` member variable is used to connect the
generator to any component with a `put()` member function.
"""
from ns.packet.packet import Packet


class PacketDistGenerator:
    """ Generates packets with a given inter-arrival time distribution.
        Set the "out" member variable to the entity to receive the packet.

        Parameters
        ----------
        env: simpy.Environment
            the simulation environment
        adist: function
            a no-parameter function that returns the successive inter-arrival times of the packets
        sdist: function
            a no-parameter function that returns the successive sizes of the packets
        initial_delay: number
            Starts generation after an initial delay. Default = 0
        finish: number
            Stops generation at the finish time. Default is infinite
    """
    def __init__(self,
                 env,
                 element_id,
                 adist,
                 sdist,
                 initial_delay=0,
                 finish=float("inf"),
                 flow_id=0,
                 rec_flow=0):
        self.element_id = element_id
        self.env = env
        self.adist = adist
        self.sdist = sdist
        self.initial_delay = initial_delay
        self.finish = finish
        self.out = None
        self.packets_sent = 0
        self.action = env.process(
            self.run())  # starts the run() method as a SimPy process
        self.flow_id = flow_id

        self.rec_flow = rec_flow
        self.time_rec = []
        self.size_rec = []

    def run(self):
        """The generator function used in simulations.
        """
        yield self.env.timeout(self.initial_delay)
        while self.env.now < self.finish:
            # wait for next transmission
            yield self.env.timeout(self.adist())

            self.packets_sent += 1
            packet = Packet(self.env.now,
                            self.sdist(),
                            self.packets_sent,
                            src=self.element_id,
                            flow_id=self.flow_id)
            if self.rec_flow:
                self.time_rec.append(packet.time)
                self.size_rec.append(packet.size)
            self.out.put(packet)
