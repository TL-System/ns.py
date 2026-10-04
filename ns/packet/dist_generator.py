"""
Implements a packet generator that simulates the sending of packets with a
specified inter- arrival time distribution and a packet size distribution. One
can set an initial delay and a finish time for packet generation. In addition,
one can set the source id and flow ids for the packets generated. The
DistPacketGenerator's `out` member variable is used to connect the generator to
any network element with a `put()` member function.
"""

import math

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
        A no-parameter function that returns the successive inter-arrival times
        of the packets, in seconds. Values must be finite and nonnegative.
        Zero allows simultaneous arrivals; unbounded traffic must eventually
        advance simulation time.
    size_dist: function
        A no-parameter function that returns the successive sizes of the
        packets in bytes. Values must be finite and nonnegative; zero-byte
        packets consume packet IDs but do not spend the byte budget.
    initial_delay: number
        Starts generation after an initial delay. Defaults to 0.
    finish: number
        Absolute, exclusive stop time in seconds. Defaults to infinite.
    size: number
        Total byte budget. The last packet is shortened to the remaining bytes.
        Defaults to unlimited; zero generates no packets.
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
        self.finish = float("inf") if finish is None else finish
        self.size = float("inf") if size is None else size
        if not math.isfinite(initial_delay) or initial_delay < 0:
            raise ValueError("initial_delay must be finite and nonnegative.")
        if math.isnan(self.finish) or self.finish < 0:
            raise ValueError("finish must be nonnegative.")
        if math.isnan(self.size) or self.size < 0:
            raise ValueError("size must be a nonnegative byte budget.")
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
        """Send at start, then wait between packets; never wait past finish."""
        delay = min(self.initial_delay, max(0, self.finish - self.env.now))
        yield self.env.timeout(delay)

        while self.env.now < self.finish and self.sent_size < self.size:
            packet_size = self.size_dist()
            if not math.isfinite(packet_size) or packet_size < 0:
                raise ValueError("packet size must be finite and nonnegative.")
            # Packet sizes and the application budget are both measured in bytes.
            packet_size = min(packet_size, self.size - self.sent_size)
            packet = Packet(
                self.env.now,
                packet_size,
                self.packets_sent,
                src=self.element_id,
                flow_id=self.flow_id,
            )

            # Register the emission before synchronous forwarding: downstream
            # elements may change packet metadata, but cannot change our budget.
            self.packets_sent += 1
            self.sent_size += packet_size

            if self.rec_flow:
                self.time_rec.append(packet.time)
                self.size_rec.append(packet_size)

            if self.debug:
                print(
                    f"DistPacketGenerator {self.element_id} sent "
                    f"packet {packet.packet_id} with size {packet.size}, "
                    f"flow_id {packet.flow_id} at time {self.env.now:.4f}."
                )

            self.out.put(packet)

            # Completion must not consume a draw or leave a future source event.
            if self.sent_size >= self.size:
                return
            interval = self.arrival_dist()
            if not math.isfinite(interval) or interval < 0:
                raise ValueError("arrival interval must be finite and nonnegative.")
            yield self.env.timeout(min(interval, self.finish - self.env.now))
