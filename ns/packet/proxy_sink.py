"""
Implements a ProxySink, designed to forward packets to a real-world TCP server, observing
arrival times from the ns.py simulation session.
"""
import socket
import threading
import time
from collections import defaultdict as dd
from select import select

import simpy

from ns.packet.packet import Packet


class ProxySink:
    """ A ProxySink is designed to forward packets to a real-world TCP server, while observing
    arrival times from the ns.py simulation session.

    Parameters
    ----------
    env: simpy.Environment
        the simulation environment
    element_id: str
        a string that serves as the ID of this element for debugging purposes.
    destination: Tuple
        a tuple that includes the hostname and port number of the real-world destination server
        where packets should be relayed to.
    packet_size: int
        the size of each packet when receiving real-world traffic.
    rec_arrivals: bool
        if True, arrivals will be recorded
    absolute_arrivals: bool
        if True absolute `arrival times will be recorded, otherwise the time between
        consecutive arrivals is recorded.
    rec_waits: bool
        if True, the waiting times experienced by the packets are recorded
    rec_flow_ids: bool
        if True, the flow IDs that the packets are used as the index for recording;
        otherwise, the 'src' field in the packets are used
    debug: bool
        If True, prints more verbose debug information.
    """
    def __init__(self,
                 env,
                 element_id: str,
                 destination,
                 packet_size: int = 4096,
                 rec_arrivals: bool = False,
                 absolute_arrivals: bool = False,
                 rec_waits: bool = False,
                 rec_flow_ids: bool = False,
                 debug: bool = False):
        self.store = simpy.Store(env)
        self.env = env
        self.element_id = element_id
        self.init_realtime = time.time()
        self.destination = destination
        self.packet_size = packet_size
        self.rec_waits = rec_waits
        self.rec_flow_ids = rec_flow_ids
        self.rec_arrivals = rec_arrivals
        self.absolute_arrivals = absolute_arrivals
        self.waits = dd(list)
        self.arrivals = dd(list)
        self.packets_received = dd(lambda: 0)
        self.bytes_received = dd(lambda: 0)
        self.packet_sizes = dd(list)
        self.packet_times = dd(list)
        self.perhop_times = dd(list)

        self.first_arrival = dd(lambda: 0)
        self.last_arrival = dd(lambda: 0)

        self.debug = debug
        self.out = None

        self.flow_ids = {}
        self.sockets = {}

        self.last_response_time = 0
        self.last_response_realtime = 0
        self.responses_sent = 0

        self.action = env.process(self.run())

    def on_accept(self, packet):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            server_sock.connect(self.destination)
        except socket.timeout:
            print(f'Timed out connecting to server {self.destination}.')

        self.flow_ids[server_sock] = packet.flow_id
        self.sockets[packet.flow_id] = server_sock

    def on_close(self, sock):
        print(f"{sock.getpeername()} has disconnected.")

        flow_id = self.flow_ids[sock]
        del self.flow_ids[sock]
        del self.sockets[flow_id]

        sock.close()

    def send_to_app(self, packet):
        """ Sends a packet to the application-layer real-world server. """
        server_sock = self.sockets[packet.flow_id]
        server_sock.send(packet.payload)

    def run(self):
        """The generator function used in simulations."""
        while True:
            input_ready, __, __ = select(list(self.flow_ids.keys()), [], [],
                                         0.1)

            for selected_sock in input_ready:
                data = selected_sock.recv(self.packet_size)

                if not data:
                    self.on_close(selected_sock)
                else:
                    if self.debug:
                        print(f"{self.element_id} received response from "
                              f"{selected_sock.getpeername()}: {data}")

                    # wait for the appropriate time to transmit a new packet with payload
                    if self.last_response_time > 0:
                        current_realtime = time.time()
                        inter_arrival_time = self.env.now - self.last_response_time
                        inter_arrival_realtime = current_realtime - self.last_response_realtime
                        self.last_response_time = self.env.now
                        self.last_response_realtime = current_realtime

                        assert inter_arrival_realtime > inter_arrival_time

                        yield self.env.timeout(inter_arrival_realtime -
                                               inter_arrival_time)

                    self.responses_sent += 1
                    packet = Packet(self.env.now,
                                    self.packet_size,
                                    self.responses_sent,
                                    realtime=time.time() - self.init_realtime,
                                    flow_id=self.flow_ids[selected_sock],
                                    payload=data)

                    if self.debug:
                        print(
                            f"{self.element_id} sent packet {packet.packet_id} "
                            f"with flow_id {packet.flow_id} at time {self.env.now}."
                        )

                    self.out.put(packet)

            if not input_ready:
                # If there are no ready sockets, yield to the other simulated elements
                yield self.env.timeout(time.time() - self.init_realtime -
                                       self.env.now)

    def put(self, packet):
        """ Sends a packet to this element. """
        now = self.env.now

        if packet.flow_id not in self.flow_ids.values():
            # new client arrived, establishing a new connection to the server
            self.on_accept(packet)

        packet_delay = now - packet.time
        packet_delay_realtime = time.time() - packet.realtime

        delayed_action = threading.Timer(packet_delay - packet_delay_realtime,
                                         self.send_to_app,
                                         args=[packet])
        delayed_action.start()

        if self.rec_flow_ids:
            rec_index = packet.flow_id
        else:
            rec_index = packet.src

        if self.rec_waits:
            self.waits[rec_index].append(packet_delay)
            self.packet_sizes[rec_index].append(packet.size)
            self.packet_times[rec_index].append(packet.time)
            self.perhop_times[rec_index].append(packet.perhop_time)

        if self.rec_arrivals:
            self.arrivals[rec_index].append(now)
            if len(self.arrivals[rec_index]) == 1:
                self.first_arrival[rec_index] = now

            if not self.absolute_arrivals:
                self.arrivals[rec_index][
                    -1] = now - self.last_arrival[rec_index]

            self.last_arrival[rec_index] = now

        if self.debug:
            print("At time {:.2f}, packet {:d} arrived.".format(
                now, packet.packet_id))
            if self.rec_waits and len(self.packet_sizes[rec_index]) >= 10:
                bytes_received = sum(self.packet_sizes[rec_index][-9:])
                time_elapsed = self.env.now - (
                    self.packet_times[rec_index][-10] +
                    self.waits[rec_index][-10])
                if time_elapsed > 0:
                    print(
                        "Average throughput (last 10 packets): {:.2f} bytes/second."
                        .format(bytes_received / time_elapsed))

        self.packets_received[rec_index] += 1
        self.bytes_received[rec_index] += packet.size
