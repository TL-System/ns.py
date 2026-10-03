"""
Implements a port with an output buffer, given an output rate and a buffer size (in either bytes
or the number of packets). This implementation uses the simple tail-drop mechanism to drop packets.
"""

import simpy


class Port:
    """Models an output port on a switch with a given rate and buffer size (in either bytes
    or the number of packets), using the simple tail-drop mechanism to drop packets.

    Parameters
    ----------
    env: simpy.Environment
        the simulation environment.
    rate: float
        the bit rate of the port (0 for unlimited).
    element_id: int
        the element id of this port.
    qlimit: integer (or None)
        a capacity in bytes or packets, including local service and packets retained
        for downstream backpressure. An exact fit is accepted; None is unlimited
        and zero provides zero capacity.
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

    def __init__(
        self,
        env,
        rate: float,
        qlimit: int = None,
        limit_bytes: bool = False,
        zero_downstream_buffer: bool = False,
        element_id: int = None,
        debug: bool = False,
    ):
        self.store = simpy.Store(env)
        self.rate = rate
        self.env = env
        self.out = None
        self.packets_received = 0
        self.packets_dropped = 0
        self.qlimit = qlimit
        self.limit_bytes = limit_bytes
        # All resident bytes: queued, in local service, or retained downstream.
        # Admission uses this total; monitors may subtract busy_packet_size to
        # show only queued/retained bytes. Release each admitted packet once.
        self.byte_size = 0
        # Includes normal departures and zero-buffer downstream releases.
        self._packets_removed = 0
        self.element_id = element_id

        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_store = simpy.Store(env)

        self.debug = debug
        self.busy = 0  # used to track if a packet is currently being sent
        self.busy_packet_size = 0

        self.action = env.process(self.run())

    def update(self, packet):
        """
        Release accounting after the downstream node removes a retained packet.

        The zero-buffer handoff calls this once per packet, after removing it from
        upstream_store. Local serialization has already completed at that point.
        """
        self.byte_size -= packet.size
        self._packets_removed += 1
        if self.debug:
            print(
                f"Port: Retrieved Packet {packet.packet_id} from flow {packet.flow_id}."
            )

    def run(self):
        """Wait for FIFO work, then serialize it; rate zero adds no service delay."""
        while True:
            if self.zero_downstream_buffer:
                packet = yield self.downstream_store.get()
            else:
                packet = yield self.store.get()

            self.busy = 1
            self.busy_packet_size = packet.size

            if self.rate > 0:
                # Packet sizes are bytes; multiplying by 8 converts to link bits.
                yield self.env.timeout(packet.size * 8.0 / self.rate)

            # Service has ended even if out.put() synchronously injects new work.
            self.busy = 0
            self.busy_packet_size = 0

            if self.zero_downstream_buffer:
                # The shared store still owns this packet until downstream removes
                # it and calls update(), possibly synchronously inside out.put().
                self.out.put(
                    packet, upstream_update=self.update, upstream_store=self.store
                )
            else:
                self.byte_size -= packet.size
                self._packets_removed += 1
                self.out.put(packet)

    def put(self, packet):
        """Sends a packet to this element."""
        self.packets_received += 1

        byte_count = self.byte_size + packet.size
        # A pending Store.get() can remove an arrival before run() resumes and
        # marks it busy. Count accepted arrivals minus releases rather than store
        # items, so a same-time burst cannot slip through that handoff. This count
        # includes the arriving packet because packets_received was just updated.
        packet_count = (
            self.packets_received - self.packets_dropped - self._packets_removed
        )

        if self.element_id is not None:
            packet.perhop_time[self.element_id] = self.env.now

        exceeds_limit = self.qlimit is not None and (
            byte_count > self.qlimit if self.limit_bytes else packet_count > self.qlimit
        )
        if exceeds_limit:
            self.packets_dropped += 1
            if self.debug:
                print(
                    f"Packet dropped: flow id = {packet.flow_id} and packet id = {packet.packet_id}"
                )
        else:
            # If the packet has not been dropped, record the queue length at this port
            if self.debug:
                print(f"Queue length at port: {len(self.store.items)} packets.")

            self.byte_size += packet.size

            if self.zero_downstream_buffer:
                self.downstream_store.put(packet)

            return self.store.put(packet)
