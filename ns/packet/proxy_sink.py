"""Forward simulated payloads to a real server and return its socket responses."""

import socket

from ns.packet.proxy_generator import _ProxyIO
from ns.packet.sink import PacketSink


class ProxySink(_ProxyIO, PacketSink):
    """A server-side proxy with PacketSink's arrival statistics.

    Each flow owns one TCP connection or connected UDP socket, so responses
    retain their originating flow ID. Connect/send use a one-second timeout.
    ``close()`` releases all flows and cancels delayed sends. See docs/proxies.md
    for wall-clock timing, UDP receive limits, and TCP EOF constraints.
    """

    def __init__(self, env, element_id: str, destination, packet_size: int = 40960,
                 protocol: str = "tcp", rec_arrivals: bool = False,
                 absolute_arrivals: bool = False, rec_waits: bool = False,
                 rec_flow_ids: bool = False, debug: bool = False):
        PacketSink.__init__(self, env, rec_arrivals, absolute_arrivals, rec_waits,
                            rec_flow_ids, debug)
        self._init_io(env, element_id, packet_size, protocol, debug)
        self.destination = destination
        self._packet_id = 0
        self.action = env.process(self.run())

    @property
    def responses_sent(self):
        return self._packet_id

    def _inputs(self):
        return list(self.sockets.values())

    def on_tcp_accept(self, packet):
        """Open a bounded server connection (also used for connected UDP)."""
        kind = socket.SOCK_STREAM if self.protocol == "tcp" else socket.SOCK_DGRAM
        sock = socket.socket(socket.AF_INET, kind)
        try:
            sock.settimeout(self.socket_timeout)
            sock.connect(self.destination)
        except OSError:
            sock.close()
            raise
        self.flow_ids[sock] = packet.flow_id
        self.sockets[packet.flow_id] = sock

    def on_tcp_close(self, sock):
        """Close a server flow and return its TCP EOF marker to the client."""
        self._disconnect(sock)

    def _receive(self, sock):
        try:
            limit = self.packet_size if self.protocol == "tcp" else self.udp_receive_size
            data = sock.recv(limit)
        except OSError:
            self._disconnect(sock)
            return
        if self.protocol == "tcp" and not data:
            self.on_tcp_close(sock)
        else:
            self._emit(self.flow_ids[sock], data)

    def send_to_app(self, packet):
        """Send all TCP bytes, or one UDP datagram, when its deadline is due."""
        if self.closed:
            return
        if self.protocol == "tcp" and packet.payload is None:
            self._close_flow(packet.flow_id)
            return
        if packet.flow_id not in self.sockets:
            self.on_tcp_accept(packet)
        sock = self.sockets[packet.flow_id]
        try:
            if self.protocol == "tcp":
                sock.sendall(packet.payload)
            else:
                sock.send(packet.payload)
        except OSError:
            # A sendall timeout may follow a partial write: terminate the flow,
            # rather than silently claiming success or replaying duplicate bytes.
            self._disconnect(sock)

    def put(self, packet):
        """Record data arrival once and schedule real delivery in wall seconds."""
        if self.closed:
            return
        if packet.payload is not None:  # EOF is control traffic, not application data.
            PacketSink.put(self, packet)
        self._schedule(packet)
