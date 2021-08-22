"""
Implements a packet generator that forwards real-world network traffic into an ns.py simulation
session.
"""
import socket
import time
from select import select

from ns.packet.packet import Packet


class ProxyPacketGenerator:
    """ Generates packets based on real-world network traffic.

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
    def __init__(self,
                 env,
                 element_id,
                 destination,
                 listen_port=3000,
                 packet_size=4096,
                 rec_flow=False,
                 debug=False):
        self.env = env
        self.element_id = element_id
        self.packet_size = packet_size
        self.out = None
        self.packets_sent = 0
        self.last_arrival_time = 0
        self.last_arrival_realtime = 0

        self.rec_flow = rec_flow
        self.time_rec = []
        self.size_rec = []
        self.debug = debug

        self.destination = destination

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', listen_port))
        self.sock.listen()

        # Linked client/server sockets in both directions
        self.channels = {}
        self.flow_ids = {}

        self.action = env.process(self.run())

    def on_accept(self):
        client_sock, client_addr = self.sock.accept()
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            server_sock.connect(self.destination)
        except socket.timeout:
            print(f'Timed out connecting to server {self.destination}.'
                  f'Closing connection to client {client_addr}.')
            client_sock.close()
        else:
            print(f"{client_addr} has connected.")
            self.flow_ids[client_sock] = client_addr[1]
            self.flow_ids[server_sock] = self.destination[1]
            self.channels[client_sock] = server_sock
            self.channels[server_sock] = client_sock

    def on_close(self, sock):
        print(f"{sock.getpeername()} has disconnected.")
        other_sock = self.channels[sock]

        sock.close()
        other_sock.close()

        del self.channels[sock]
        del self.channels[other_sock]

    def run(self):
        """The generator function used in simulations."""
        while True:
            # receiving data from the listening TCP socket
            input_ready, __, __ = select([self.sock] +
                                         list(self.channels.keys()), [], [])
            for selected_sock in input_ready:
                if selected_sock == self.sock:
                    self.on_accept()
                else:
                    data = selected_sock.recv(self.packet_size)
                    if not data:
                        self.on_close(selected_sock)
                    else:
                        print(
                            f"Received data from {selected_sock.getpeername()}: {data}"
                        )

                        # wait for the appropriate time to transmit a new packet with payload
                        if self.last_arrival_time > 0:
                            current_realtime = time.process_time()
                            inter_arrival_time = self.env.now - self.last_arrival_time
                            inter_arrival_realtime = current_realtime - self.last_arrival_realtime
                            self.last_arrival_time = self.env.now
                            self.last_arrival_realtime = current_realtime

                            assert inter_arrival_realtime > inter_arrival_time

                            yield self.env.timeout(inter_arrival_realtime -
                                                   inter_arrival_time)

                        self.packets_sent += 1
                        packet = Packet(
                            self.env.now,
                            self.packet_size,
                            self.packets_sent,
                            realtime=time.process_time(),
                            src=self.element_id,
                            flow_id=self.flow_ids[selected_sock],
                            payload=data,
                            server_sock=self.channels[selected_sock])
                        if self.rec_flow:
                            self.time_rec.append(packet.time)
                            self.size_rec.append(packet.size)

                        if self.debug:
                            print(
                                f"Sent packet {packet.packet_id} with flow_id {packet.flow_id} at "
                                f"time {self.env.now}.")

                        self.out.put(packet)
