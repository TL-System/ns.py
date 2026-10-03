"""
Implements a Virtual Clock server.

Reference:

L. Zhang, "VirtualClock: A New Traffic Control Algorithm for Packet-Switched
Networks," ACM Transactions on Computer Systems, vol. 9, no. 2, pp. 101-124,
May 1991, section 3.1 (the expanded version of the SIGCOMM 1990 paper).
"""

from collections import defaultdict as dd
from collections.abc import Callable
from math import isfinite

from ns.packet.packet import Packet
from ns.utils.retained_store import remove_packet
from ns.utils import taggedstore


class VirtualClockServer:
    """Order nonpreemptive packet service by per-class reserved-rate clocks.

    This implements the paper's data-forwarding rule with an unlimited queue.
    It does not implement the AR/AI flow-monitoring feedback, periodic clock
    synchronization, or buffer-overflow policy. ``v_clocks`` retains the raw
    cumulative monitoring clock; ``aux_vc`` supplies scheduling tags in seconds.
    Tags order eligible packets but never delay service on an otherwise idle link.

    Parameters
    ----------
    env: simpy.Environment
        The simulation environment.
    rate: float
        The bit rate of the port.
    vticks: list or dict
        Positive, finite seconds per bit: the inverse of each class's reserved
        rate in bits/second. A list uses integer class IDs as indices; a dictionary
        maps class IDs to vticks. All flows mapped to a class share its clock.
    flow_classes: function
        Maps each packet to a configured class ID. The default uses its flow_id,
        giving each flow a separate Virtual Clock.
    zero_buffer: bool
        Does this server have a zero-length buffer? This is useful when multiple
        basic elements need to be put together to construct a more complex element
        with a unified buffer.
    zero_downstream_buffer: bool
        Does this server's downstream element has a zero-length buffer? If so, packets
        may queue up in this element's own buffer rather than be forwarded to the
        next-hop element.
    debug: bool
        If True, prints more verbose debug information.
    """

    def __init__(
        self,
        env,
        rate,
        vticks,
        flow_classes: Callable = lambda p: p.flow_id,
        zero_buffer=False,
        zero_downstream_buffer=False,
        debug: bool = False,
    ):
        self.env = env
        self.rate = rate
        self.vticks = vticks

        self.flow_classes = flow_classes

        self.aux_vc = {}
        self.v_clocks = {}
        self.flow_queue_count = {}

        if isinstance(vticks, list):
            queue_ids = range(len(vticks))
        elif isinstance(vticks, dict):
            queue_ids = vticks
        else:
            raise ValueError("vticks must be either a list or a dictionary.")

        for queue_id in queue_ids:
            if not isfinite(vticks[queue_id]) or vticks[queue_id] <= 0:
                raise ValueError("Each vtick must be positive and finite.")
            self.aux_vc[queue_id] = 0.0
            self.v_clocks[queue_id] = 0.0
            self.flow_queue_count[queue_id] = 0

        self.out = None
        self.packets_received = 0
        self.packets_dropped = 0
        self.debug = debug

        self.current_packet = None
        self.byte_sizes = dd(lambda: 0)

        self.upstream_updates = {}
        self.upstream_stores = {}
        self.zero_buffer = zero_buffer
        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_store = taggedstore.TaggedStore(env)

        self.store = taggedstore.TaggedStore(env)
        # Wake the process without reserving a packet before service selection.
        self._wakeup = env.event()
        self.action = env.process(self.run())

    def update_stats(self, packet):
        """Remove a packet from waiting telemetry when local service starts.

        The packet in service is reported separately by packet_in_service().
        Downstream retention does not count as waiting for this server either.
        """
        class_id = self.flow_classes(packet)
        self.flow_queue_count[class_id] -= 1
        self.byte_sizes[class_id] -= packet.size

        if self.debug:
            print(
                f"Started Packet {packet.packet_id} from flow {packet.flow_id} "
                f"belonging to class {class_id} at time {self.env.now}"
            )

    def update(self, packet):
        """
        The packet has just been retrieved from this element's own buffer by a downstream
        node that has no buffers. Propagate to the upstream if this node also has a zero-buffer
        configuration.
        """
        if self.zero_buffer and packet in self.upstream_stores:
            # Clear hooks before callbacks, which may synchronously revisit us.
            store = self.upstream_stores.pop(packet)
            callback = self.upstream_updates.pop(packet)
            remove_packet(store, packet)
            callback(packet)

    def packet_in_service(self) -> Packet:
        """
        Returns the packet that is currently being sent to the downstream element.
        Used by a ServerMonitor.
        """
        return self.current_packet

    def byte_size(self, queue_id) -> int:
        """
        Returns bytes waiting for local service in a flow class.
        Used by a ServerMonitor.
        """
        return self.byte_sizes.get(queue_id, 0)

    def size(self, queue_id) -> int:
        """
        Returns packets waiting for local service in a flow class.
        Used by a ServerMonitor; the packet in service is counted separately.
        """
        return self.flow_queue_count.get(queue_id, 0)

    def all_flows(self) -> list:
        """
        Returns observed class IDs (flow IDs with the default mapping).
        """
        return list(self.byte_sizes)

    def run(self):
        """Wait for work, select the smallest tag, then serialize one packet.

        Service is nonpreemptive. A zero-time wait before each selection lets
        arrivals already scheduled at a completion time join the next decision.
        It does not impose global phases on arbitrary chains of user processes.
        """
        queue = self.downstream_store if self.zero_downstream_buffer else self.store
        while True:
            if not queue.items:
                self._wakeup = self.env.event()
                yield self._wakeup

            # Do not leave a pending get() on an idle heap: it could select an
            # arrival before other arrivals at the same time have been queued.
            yield self.env.timeout(0)
            packet = yield queue.get()
            self.current_packet = packet
            self.update_stats(packet)
            # Packet sizes are bytes; convert to bits for link serialization.
            yield self.env.timeout(packet.size * 8.0 / self.rate)

            # Synchronous downstream callbacks should observe completed service.
            self.current_packet = None
            if self.zero_downstream_buffer:
                # The shared store retains ownership until downstream pulls it.
                self.out.put(
                    packet, upstream_update=self.update, upstream_store=self.store
                )
            else:
                self.update(packet)
                self.out.put(packet)

    def put(self, packet, upstream_update=None, upstream_store=None):
        """Stamp an arrival in seconds and enqueue it for local service."""
        class_id = self.flow_classes(packet)
        # Resolve the configured class before changing any admission accounting.
        previous_tag = self.aux_vc[class_id]
        vtick = self.vticks[class_id]
        now = self.env.now

        if class_id not in self.byte_sizes:
            self.v_clocks[class_id] = now

        # Section 3.1 advances both clocks by the packet's reserved service time.
        # Seconds/bit * bytes * 8 bits/byte gives seconds, even for mixed sizes.
        tick = vtick * packet.size * 8.0
        self.v_clocks[class_id] += tick
        # An idle class earns no credit from silence. Preserve a clock ahead of
        # real time, but bring a lagging scheduling clock up to this arrival.
        tag = max(now, previous_tag) + tick
        self.aux_vc[class_id] = tag

        self.packets_received += 1
        self.byte_sizes[class_id] += packet.size
        self.flow_queue_count[class_id] += 1

        if self.debug:
            print(
                f"Packet arrived at {self.env.now}, with flow_id {packet.flow_id}, "
                f"belonging to class {class_id}, packet_id {packet.packet_id}, "
                f"virtual clock {self.v_clocks[class_id]}, aux_vc {tag}"
            )

        if (
            self.zero_buffer
            and upstream_update is not None
            and upstream_store is not None
        ):
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update

        if self.zero_downstream_buffer:
            self.downstream_store.put((tag, packet))

        admitted = self.store.put((tag, packet))
        if not self._wakeup.triggered:
            self._wakeup.succeed()
        return admitted
