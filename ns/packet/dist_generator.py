"""
Implements a packet generator that simulates the sending of packets with a specified inter-
arrival time distribution and a packet size distribution. One can set an initial delay and
a finish time for packet generation. In addition, one can set the source id and flow ids for
the packets generated. The DistPacketGenerator's `out` member variable is used to connect the
generator to any network element with a `put()` member function.
"""

from ns.packet.packet import Packet


class DistPacketGenerator:
    """Generates packets with a given inter-arrival time distribution.

    Parameters
    ----------
    env: simpy.Environment
        The simulation environment.
    element_id: str
        the ID of this element.
    arrival_dist: function
        A no-parameter function that returns the successive inter-arrival times of
        the packets.
    size_dist: function
        A no-parameter function that returns the successive sizes of the packets.
    initial_delay: number
        Starts generation after an initial delay. Defaults to 0.
    finish: number
        Stops generation at the finish time. Defaults to infinite.
    rec_flow: bool
        Are we recording the statistics of packets generated?
    """

    def __init__(
        self,
        env,
        element_id,
        arrival_dist,
        size_dist,
        initial_delay=0,
        finish=None,
        size=None,
        flow_id=0,
        rec_flow=False,
        debug=False,
    ):
        self.element_id = element_id
        self.env = env
        self.arrival_dist = arrival_dist
        self.size_dist = size_dist
        self.initial_delay = initial_delay
        self.finish = float("inf") if finish == None else finish
        self.size = float("inf") if size == None else size
        self.out = None
        self.packets_sent = 0
        self.sent_size = 0
        self.action = env.process(self.run())
        self.flow_id = flow_id

        self.rec_flow = rec_flow
        self.time_rec = []
        self.size_rec = []
        self.debug = debug

    def run(self):
        """The generator function used in simulations."""
        yield self.env.timeout(self.initial_delay)

        while self.env.now < self.finish and self.sent_size < self.size:
            packet = Packet(
                self.env.now,
                self.size_dist(),
                self.packets_sent,
                src=self.element_id,
                flow_id=self.flow_id,
            )

            # wait for next transmission
            yield self.env.timeout(self.arrival_dist())
            self.out.put(packet)

            self.packets_sent += 1
            self.sent_size += packet.size

            if self.rec_flow:
                self.time_rec.append(packet.time)
                self.size_rec.append(packet.size)

            if self.debug:
                print(
                    "DistPacketGenerator {} sent packet {:d} with size {:d}, "
                    "flow_id {:d} at time {:.4f}.".format(
                        self.element_id,
                        packet.packet_id,
                        packet.size,
                        packet.flow_id,
                        self.env.now,
                    )
                )
