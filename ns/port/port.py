"""
Models a first-in, first-out (FIFO) queued output port on a packet switch/router.
You can set the rate of the output port and a queue size limit (in bytes). Keeps
track of packets received and packets dropped.
"""
import simpy


class SwitchPort:
    """ Models a switch output port with a given rate and buffer size limit in bytes.
        Set the "out" member variable to the entity to receive the packet.

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        rate : float
            the bit rate of the port
        qlimit : integer (or None)
            a buffer size limit in bytes or packets for the queue (including items
            in service).
        limit_bytes : If true, the queue limit will be based on bytes if false the
            queue limit will be based on packets.
    """
    def __init__(self,
                 env,
                 rate,
                 qlimit=None,
                 limit_bytes=True,
                 zero_downstream_buffer=False,
                 debug=False,
                 node_id=None):
        self.store = simpy.Store(env)
        self.rate = rate
        self.env = env
        self.out = None
        self.packets_rec = 0
        self.packets_dropped = 0
        self.qlimit = qlimit
        self.limit_bytes = limit_bytes
        self.byte_size = 0  # Current size of the queue in bytes
        self.node_id = node_id

        self.qlen_numbers = []
        self.qlen_bytes = []
        self.qlen_numbers_rec = []
        self.qlen_bytes_rec = []
        self.packets_dropped_index = []

        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_store = simpy.Store(env)

        self.debug = debug
        self.busy = 0  # Used to track if a packet is currently being sent
        self.busy_packet_size = 0

        self.action = env.process(
            self.run())  # starts the run() method as a SimPy process

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
        """ Sends the packet 'pkt' to the next-hop element. """
        self.qlen_numbers.append(len(self.store.items))
        self.qlen_bytes.append(self.byte_size)

        self.packets_rec += 1
        tmp_byte_count = self.byte_size + pkt.size

        if self.node_id is not None:
            pkt.perhoptime[self.node_id] = self.env.now

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
