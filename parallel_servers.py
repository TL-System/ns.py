import random
from functools import partial
import matplotlib.pyplot as plt
import simpy
from collections import defaultdict as dd

from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.sink import PacketSink
from ns.port.port import Port
from ns.packet.packet import Packet


class ParallelServers:
    """
    K parallel servers (channels) with zero buffer.

    """

    def __init__(
        self,
        env,
        K: int,
        server_rate: float,
        zero_buffer: bool = True,
        zero_downstream_buffer: bool = False,
        debug: bool = False,
    ):
        self.env = env
        self.store = simpy.Store(env)
        self.out = None
        self.zero_buffer = zero_buffer

        # self.packets_available = simpy.Store(env)
        self.packets_received = 0
        self.current_packet = None

        self.K = K  # the number of parallel servers
        self.servers_rate = [
            server_rate
        ] * K  # services rate of all servers, in future, could be of different values

        # track the status of busy channels
        # key: server_index; value: 0 for idle, 1 for busy
        self.all_channels = dict(zip(list(range(self.K)), [0] * self.K))

        # index of the assigned channel to a pkt
        self.assigned_channel = dd(lambda: 0)

        # count #pkts sent by each channel
        self.all_channels_count = dict(zip(list(range(self.K)), [0] * self.K))
        # count #bytes sent by each channel
        self.all_channels_byte_count = dict(zip(list(range(self.K)), [0] * self.K))

        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_store = {}

        self.upstream_updates = {}
        self.upstream_stores = {}

        self.debug = debug
        self.action = env.process(self.run())

    def update_stats(self, packet):
        """
        The packet has been sent (or authorized to be sent if the downstream node has a zero-buffer
        configuration), we need to update the internal statistics related to this event.
        """

        self.all_channels[self.assigned_channel[packet]] = 0

        if self.debug:
            print(
                f"Sent out via channel {self.assigned_channel[packet]}: flow id = {packet.flow_id}, packet id = {packet.packet_id}\n"
            )
            print(f"channel status changed to {self.all_channels}")

    def update(self, packet):
        """
        The packet has just been retrieved from this element's own buffer by a downstream
        node that has no buffers.
        """
        # With no local buffers, this element needs to pull the packet from upstream
        if self.zero_buffer:
            # For each packet, remove it from its own upstream's store
            # print(f"upstream_stores: {self.upstream_stores.items()}")
            self.upstream_stores[packet].get()
            del self.upstream_stores[packet]
            self.upstream_updates[packet](packet)
            del self.upstream_updates[packet]

        if self.debug:
            print(
                f"Parallel Server: Retrieved Packet {packet.packet_id} from flow {packet.flow_id}."
            )

    def packet_in_service(self) -> Packet:
        """
        Returns the packet that is currently being sent to the downstream element.
        Used by a ServerMonitor.
        """
        return self.current_packet

    def run(self):
        """The generator function used in simulations."""
        while True:
            while sum(self.all_channels.values()) < self.K:
                if self.zero_downstream_buffer:
                    packet = yield self.downstream_store.get()
                    self.current_packet = packet

                    yield self.env.timeout(
                        packet.size
                        * 8.0
                        / self.servers_rate[self.assigned_channel[packet]]
                    )

                    self.out.put(
                        packet, upstream_update=self.update, upstream_store=self.store
                    )
                    self.current_packet = None
                    self.update_stats(packet)
                else:
                    packet = yield self.store.get()
                    self.current_packet = packet

                    yield self.env.timeout(
                        packet.size
                        * 8.0
                        / self.servers_rate[self.assigned_channel[packet]]
                    )

                    self.update(packet)
                    self.out.put(packet)
                    self.current_packet = None
                    self.update_stats(packet)

    def put(self, packet, upstream_update=None, upstream_store=None):
        """Sends a packet to this element."""
        self.packets_received += 1
        flow_id = packet.flow_id

        now = self.env.now

        if sum(self.all_channels.values()) >= self.K:
            if self.debug:
                print("All servers are busy")
        else:
            # If the packet has not been blocked, record the assigned channel
            for server_id in self.all_channels.keys():
                if self.all_channels[server_id] == 0:
                    self.assigned_channel[packet] = server_id
                    print(f"selected server_id {server_id}")
                    break
            if self.debug:
                print(
                    f"\nPacket arrived at parallel servers at time {self.env.now}, \nflow_id = {flow_id}, packet_id = {packet.packet_id}, assigned server_id = {self.assigned_channel[packet]}\n"
                )

            self.all_channels[self.assigned_channel[packet]] = 1

            print(f"after put, all_channels = {self.all_channels}")
            self.all_channels_count[self.assigned_channel[packet]] += 1
            self.all_channels_byte_count[self.assigned_channel[packet]] += packet.size

            if (
                self.zero_buffer
                and upstream_update is not None
                and upstream_store is not None
            ):
                self.upstream_stores[packet] = upstream_store
                self.upstream_updates[packet] = upstream_update

            if self.zero_downstream_buffer:
                self.downstream_store.put(packet)

            return self.store.put(packet)


def const_arrival():
    """
    inter-arrival time distribution (sec)
    """
    return 0.5


def const_size():
    """
    packet size distribution (byte)
    """
    return 100.0


if __name__ == "__main__":
    # Set up arrival and packet size distributions
    # arrival_dist = partial(random.expovariate,
    #                        1)  # arrival rate λ = 0.5 packets per second
    # size_dist = partial(random.expovariate, 0.01)  # mean size 100 bytes

    server_rate = 800.0  # mean port rate 800 bps per server
    K_servers = 2  # number of servers

    env = simpy.Environment()  # Create the SimPy environment
    ps = PacketSink(env, debug=True, rec_arrivals=True)
    # pg = DistPacketGenerator(env, "pg", arrival_dist, size_dist, flow_id=0)
    pg = DistPacketGenerator(
        env, "pg", const_arrival, const_size, flow_id=0, debug=True
    )

    buffer = Port(env, rate=0, qlimit=None, zero_downstream_buffer=True, debug=True)

    parallel_servers = ParallelServers(
        env, K_servers, server_rate, zero_buffer=True, debug=True
    )

    pg.out = buffer
    # buffer.out = ps
    buffer.out = parallel_servers
    parallel_servers.out = ps

    env.run(until=20)

    print(
        f"\nSimulation Done...\nChannel id : packet count \n {parallel_servers.all_channels_count}"
    )

    # # Plot the waiting time histogram
    # plt.hist(ps.waits, bins=50, density=True, alpha=0.7)
    # plt.xlabel('Waiting Time')
    # plt.ylabel('Probability Density')
    # plt.title(f'M/M/{K_servers} Queue System - Waiting Time Histogram')
    # plt.show()
