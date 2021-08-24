"""
Implements a packet generator that forwards real-world network traffic into an ns.py simulation
session.
"""
import socket
import threading
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
            a string that serves as the ID of this element for debugging purposes.
        flow_id: int
            the starting point of flow IDs. Consecutive flow IDs will be assigned to new
            clients starting from this value.
        listen_port: the listening point for new connections.
        packet_size: int
            the size of each packet when receiving real-world traffic.
        debug: bool
            If True, prints more verbose debug information.        
    """
    def __init__(self,
                 env,
                 element_id: str,
                 flow_id: int = 0,
                 listen_port: int = 3000,
                 packet_size: int = 4096,
                 debug: bool = False):
        self.env = env
        self.element_id = element_id
        self.next_flow_id = flow_id
        self.packet_size = packet_size
        self.init_realtime = time.time()
        self.out = None
        self.packets_sent = 0
        self.last_arrival_time = 0
        self.last_arrival_realtime = 0

        self.debug = debug

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', listen_port))
        self.sock.listen()

        # Associating sockets to flow IDs
        self.flow_ids = {}
        self.sockets = {}

        self.action = env.process(self.run())

    def on_accept(self):
        client_sock, client_addr = self.sock.accept()
        print(f"{client_addr} has connected.")
        self.flow_ids[client_sock] = self.next_flow_id
        self.sockets[self.next_flow_id] = client_sock
        self.next_flow_id += 1

    def on_close(self, sock):
        print(f"{sock.getpeername()} has disconnected.")

        flow_id = self.flow_ids[sock]
        del self.flow_ids[sock]
        del self.sockets[flow_id]

        sock.close()

    def remove_closed_sockets(self):
        closed_flow_id = -1

        for sock in self.flow_ids:
            if sock.fileno() == -1:
                closed_sock = sock
                closed_flow_id = self.flow_ids[sock]

        if closed_flow_id != -1:
            del self.flow_ids[closed_sock]
            del self.sockets[closed_flow_id]

    def run(self):
        """The generator function used in simulations."""
        while True:
            self.remove_closed_sockets()

            # receiving data from the listening TCP socket
            input_ready, __, __ = select(
                [self.sock] + list(self.flow_ids.keys()), [], [], 0.1)

            for selected_sock in input_ready:
                if selected_sock == self.sock:
                    self.on_accept()
                else:
                    data = selected_sock.recv(self.packet_size)

                    if not data:
                        self.on_close(selected_sock)
                    else:
                        if self.debug:
                            print(f"{self.element_id} received data from "
                                  f"{selected_sock.getpeername()}: {data}")

                        # wait for the appropriate time to transmit a new packet with payload
                        if self.last_arrival_time > 0:
                            current_realtime = time.time()
                            inter_arrival_time = self.env.now - self.last_arrival_time
                            inter_arrival_realtime = current_realtime - self.last_arrival_realtime
                            self.last_arrival_time = self.env.now
                            self.last_arrival_realtime = current_realtime

                            assert inter_arrival_realtime > inter_arrival_time

                            yield self.env.timeout(inter_arrival_realtime -
                                                   inter_arrival_time)

                        self.packets_sent += 1
                        packet = Packet(self.env.now,
                                        self.packet_size,
                                        self.packets_sent,
                                        realtime=time.time() -
                                        self.init_realtime,
                                        src=self.element_id,
                                        flow_id=self.flow_ids[selected_sock],
                                        payload=data)

                        if self.debug:
                            print(
                                f"{self.element_id} sent packet {packet.packet_id} with "
                                f"flow_id {packet.flow_id} at time {self.env.now}."
                            )

                        self.out.put(packet)

            if not input_ready:
                # If there are no ready sockets, yield to the other simulated elements
                yield self.env.timeout(time.time() - self.init_realtime -
                                       self.env.now)

    def send_to_app(self, packet):
        """ Sends a packet to the application-layer real-world client. """
        client_sock = self.sockets[packet.flow_id]
        client_sock.send(packet.payload)

    def put(self, packet):
        """ Sends a packet to this element. """
        now = self.env.now

        packet_delay = now - packet.time
        packet_delay_realtime = time.time() - packet.realtime

        delayed_action = threading.Timer(packet_delay - packet_delay_realtime,
                                         self.send_to_app,
                                         args=[packet])
        delayed_action.start()
