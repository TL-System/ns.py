"""
Implements a port with an output buffer with a given output rate and buffer size (in either bytes
or the number of packets), using the simple tail-drop mechanism to drop packets.
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

        self.qlen_numbers = []
        self.qlen_bytes = []
        self.qlen_numbers_rec = []
        self.qlen_bytes_rec = []
        self.packets_dropped_index = []

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

    def put(self, pkt):
        """ Sends the packet 'pkt' to this element. """
        self.qlen_numbers.append(len(self.store.items))
        self.qlen_bytes.append(self.byte_size)

        self.packets_received += 1
        byte_count = self.byte_size + pkt.size

        if self.element_id is not None:
            pkt.perhop_time[self.element_id] = self.env.now

        if self.qlimit is None:
            self.byte_size = byte_count
            if self.zero_downstream_buffer:
                self.downstream_store.put(pkt)
            return self.store.put(pkt)

        if self.limit_bytes and byte_count >= self.qlimit:
            self.packets_dropped += 1
            self.packets_dropped_index.append((pkt.flow_id, pkt.id))
            if self.debug:
                print(f"Packet dropped. Flow ID {pkt.flow_id}, ID {pkt.id}")
        elif not self.limit_bytes and len(self.store.items) >= self.qlimit - 1:
            self.packets_dropped += 1
            self.packets_dropped_index.append((pkt.flow_id, pkt.id))
            if self.debug:
                print(f"Packet dropped. Flow ID {pkt.flow_id}, ID {pkt.id}")
        else:
            # If the packet has not been dropped, keep its queue length
            self.qlen_numbers_rec.append(len(self.store.items))
            self.qlen_bytes_rec.append(self.byte_size)

            self.byte_size = byte_count

            if self.zero_downstream_buffer:
                self.downstream_store.put(pkt)

            return self.store.put(pkt)
