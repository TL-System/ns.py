"""
Models an output port on a switch with a given rate and buffer size (in either bytes
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
            a buffer size limit in bytes or packets for the queue (including items
            in service).
        limit_bytes: bool
            if true, the queue limit will be based on bytes if false the queue limit
            will be based on packets.
        zero_downstream_buffer: bool
            if true, assume that the downstream element does not have any buffers,
            and backpressure is in effect so that all waiting packets queue up in this
            element's buffer.
        debug: bool
            if true, print more debugging information.
    """
    def __init__(self,
                 env,
                 rate: float,
                 element_id: int = None,
                 qlimit: int = None,
                 limit_bytes: bool = True,
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
        self.byte_size -= packet.size

    def run(self):
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
        tmp_byte_count = self.byte_size + pkt.size

        if self.element_id is not None:
            pkt.perhop_time[self.element_id] = self.env.now

        if self.qlimit is None:
            self.byte_size = tmp_byte_count
            if self.zero_downstream_buffer:
                self.downstream_store.put(pkt)
            return self.store.put(pkt)

        if self.limit_bytes and tmp_byte_count >= self.qlimit:
            self.packets_dropped += 11
            self.packets_dropped_index.append((pkt.flow_id, pkt.id))
            if self.debug:
                print(f"Packet dropped. Flow ID {pkt.flow_id}, ID {pkt.id}")
        elif not self.limit_bytes and len(self.store.items) >= self.qlimit - 1:
            self.packets_dropped += 11
            self.packets_dropped_index.append((pkt.flow_id, pkt.id))
            if self.debug:
                print(f"Packet dropped. Flow ID {pkt.flow_id}, ID {pkt.id}")
        else:
            self.qlen_numbers_rec.append(len(
                self.store.items))  # if not dropped, keep its queue length
            self.qlen_bytes_rec.append(self.byte_size)

            self.byte_size = tmp_byte_count

            if self.zero_downstream_buffer:
                self.downstream_store.put(pkt)

            return self.store.put(pkt)
