"""
Implements a port with an output buffer, given an output rate and a buffer size (in either bytes
or the number of packets). This implementation uses the simple tail-drop mechanism to drop packets.
"""
import simpy


class Port:
    """ Models an output port on a switch with a given rate and buffer size (in either bytes
        or the number of packets), using the simple tail-drop mechanism to drop packets.

        Parameters
        ----------
        env: simpy.Environment
            the simulation environment
        rate: float
            the bit rate of the port
        element_id: int
            the element id of this port
        qlimit: integer (or None)
            a queue limit in bytes or packets (including the packet in service), beyond
            which all packets will be dropped.
        limit_bytes: bool
            if True, the queue limit will be based on bytes; if False, the queue limit
            will be based on packets.
        zero_downstream_buffer: bool
            if True, assume that the downstream element does not have any buffers,
            and backpressure is in effect so that all waiting packets queue up in this
            element's buffer.
        debug: bool
            If True, prints more verbose debug information.
    """
    def __init__(self,
                 env,
                 rate: float,
                 element_id: int = None,
                 qlimit: int = None,
                 limit_bytes: bool = False,
                 zero_downstream_buffer: bool = False,
                 debug: bool = False):
        self.store = simpy.Store(env)
        self.rate = rate
        self.env = env
        self.out = None
        self.packets_received = 0
        self.packets_dropped = 0
        self.qlimit = qlimit
        self.limit_bytes = limit_bytes
        self.byte_size = 0  # the current size of the queue in bytes
        self.element_id = element_id

        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_store = simpy.Store(env)

        self.debug = debug
        self.busy = 0  # used to track if a packet is currently being sent
        self.busy_packet_size = 0

        self.action = env.process(self.run())

    def update(self, packet):
        """The packet has just been retrieved from this element's own buffer, so
        update internal housekeeping states accordingly."""
        self.byte_size -= packet.size

    def run(self):
        """The generator function used in simulations."""
        while True:
            if self.zero_downstream_buffer:
                packet = yield self.downstream_store.get()
            else:
                packet = yield self.store.get()
                self.update(packet)

            self.busy = 1
            self.busy_packet_size = packet.size

            if self.rate > 0:
                yield self.env.timeout(packet.size * 8.0 / self.rate)

            if self.zero_downstream_buffer:
                self.out.put(packet,
                             upstream_update=self.update,
                             upstream_store=self.store)
            else:
                self.out.put(packet)

            self.busy = 0
            self.busy_packet_size = 0

    def put(self, packet):
        """ Sends a packet to this element. """
        self.packets_received += 1
        byte_count = self.byte_size + packet.size

        if self.element_id is not None:
            packet.perhop_time[self.element_id] = self.env.now

        if self.qlimit is None:
            self.byte_size = byte_count
            if self.zero_downstream_buffer:
                self.downstream_store.put(packet)
            return self.store.put(packet)

        if self.limit_bytes and byte_count >= self.qlimit:
            self.packets_dropped += 1
            if self.debug:
                print(
                    f"Packet dropped: flow id = {packet.flow_id} and packet id = {packet.packet_id}"
                )
        elif not self.limit_bytes and len(self.store.items) >= self.qlimit - 1:
            self.packets_dropped += 1
            if self.debug:
                print(
                    f"Packet dropped: flow id = {packet.flow_id}, packet id = {packet.packet_id}"
                )
        else:
            # If the packet has not been dropped, record the queue length at this port
            if self.debug:
                print(
                    f"Queue length at port: {len(self.store.items)} packets.")

            self.byte_size = byte_count

            if self.zero_downstream_buffer:
                self.downstream_store.put(packet)

            return self.store.put(packet)
