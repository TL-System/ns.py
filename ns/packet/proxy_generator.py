"""Bridge local application sockets to packets in a plain SimPy environment."""

import heapq
import socket
import time
from collections.abc import Generator, Hashable
from select import select
from typing import Any

import simpy

from ns.packet.packet import Packet


class _ProxyIO:
    """Small shared polling/lifetime machinery; all work stays on the SimPy thread."""

    _packet_id: int
    poll_interval = 0.01  # Seconds: bounds socket polling and delayed-send resolution.
    udp_receive_size = 65535  # Bytes: receive a whole IPv4 datagram, never truncate.
    socket_timeout = 1.0  # Seconds: bounds socket connect/send after address resolution.

    def _inputs(self) -> list[socket.socket]:
        raise NotImplementedError

    def _receive(self, sock: socket.socket) -> None:
        raise NotImplementedError

    def send_to_app(self, packet: Packet) -> None:
        raise NotImplementedError

    def _init_io(
        self, env: simpy.Environment, element_id: Hashable,
        packet_size: int, protocol: str, debug: bool,
    ) -> None:
        if protocol not in ("tcp", "udp"):
            raise ValueError("Protocol should be either 'tcp' or 'udp'.")
        if not isinstance(packet_size, int) or packet_size <= 0:
            raise ValueError("packet_size must be a positive integer receive limit.")
        self.env = env
        self.element_id = element_id
        self.packet_size = packet_size
        self.protocol = protocol
        self.debug = debug
        self.out: Any = None
        self.init_realtime = time.monotonic()
        self._init_simtime = env.now
        self.flow_ids: dict[Hashable, Hashable] = {}
        # Socket adapters in tests can supply only the operations exercised.
        self.sockets: dict[Hashable, Any] = {}
        self._retired_flows: set[Hashable] = set()
        self.closed = False
        self._pending: list[tuple[float, int, Packet]] = []
        self._send_id = 0
        self._last_deadline: dict[Hashable, float] = {}

    def _emit(self, flow_id: Hashable, payload: bytes | None) -> None:
        # Bytes, not the receive buffer limit, determine link serialization time.
        # None denotes TCP EOF; b"" remains a valid, empty UDP datagram.
        self._packet_id += 1
        packet = Packet(
            self.env.now, len(payload) if payload is not None else 0,
            self._packet_id, realtime=time.monotonic(), src=self.element_id,
            flow_id=flow_id, payload=payload,
        )
        if self.debug:
            print(f"{self.element_id}: flow {flow_id}, {packet.size} bytes "
                  f"at simulation time {self.env.now}.")
        self.out.put(packet)

    def _close_flow(self, flow_id: Hashable) -> None:
        # TCP IDs are lifetime-unique. Remember EOF/error closure even after
        # removing the socket: requests can still be traveling through SimPy.
        if self.protocol == "tcp":
            self._retired_flows.add(flow_id)
        sock = self.sockets.pop(flow_id, None)
        if sock is not None:
            self.flow_ids.pop(sock, None)
            sock.close()
        # Cancel queued sends belonging to the disconnected flow.
        self._pending = [entry for entry in self._pending
                         if entry[2].flow_id != flow_id]
        heapq.heapify(self._pending)
        self._last_deadline.pop(flow_id, None)

    def _disconnect(self, sock: socket.socket) -> None:
        flow_id = self.flow_ids.get(sock)
        if flow_id is not None:
            self._close_flow(flow_id)
            if self.protocol == "tcp":
                self._emit(flow_id, None)

    def remove_closed_sockets(self) -> None:
        """Retire every externally closed socket, including its queued work."""
        for sock in list(self.sockets.values()):
            if sock.fileno() == -1:
                self._disconnect(sock)

    def _schedule(self, packet: Packet) -> None:
        if self.closed or packet.flow_id in self._retired_flows:
            return
        # Proxy packets carry absolute monotonic wall seconds, so the two ends
        # need not have been constructed at exactly the same wall-clock instant.
        # A normal Packet's default realtime=0 makes it immediately due.
        deadline = packet.realtime + max(0, self.env.now - packet.time)
        # Preserve put order within a flow, including a close after delayed data.
        deadline = max(deadline, self._last_deadline.get(packet.flow_id, deadline))
        self._last_deadline[packet.flow_id] = deadline
        self._send_id += 1
        heapq.heappush(self._pending, (deadline, self._send_id, packet))
        self._flush()

    def _flush(self) -> None:
        while not self.closed and self._pending:
            if self._pending[0][0] > time.monotonic():
                break
            _, _, packet = heapq.heappop(self._pending)
            self.send_to_app(packet)

    def run(self) -> Generator[simpy.Event, Any, None]:
        """Poll wall sockets, then yield positive simulation seconds each round.

        Plain Environment time catches up to elapsed monotonic time. If other
        elements advance it ahead, polling still yields a small positive step;
        real sends wait for their wall deadlines rather than running early.
        """
        while not self.closed:
            self.remove_closed_sockets()
            self._flush()
            inputs = self._inputs()
            if inputs:
                ready, _, _ = select(inputs, [], [], self.poll_interval)
            else:
                # An idle sink has no sockets; empty select is not portable.
                time.sleep(self.poll_interval)
                ready = []
            for sock in ready:
                # Earlier callbacks can close another socket in this ready list.
                if not self.closed and sock.fileno() != -1:
                    self._receive(sock)
            self._flush()
            elapsed = time.monotonic() - self.init_realtime
            yield self.env.timeout(max(
                self.poll_interval, self._init_simtime + elapsed - self.env.now
            ))

    def close(self) -> None:
        """Cancel queued sends and close every owned socket; safe to call twice.

        The polling process exits at its next already scheduled wakeup. No
        background worker or timer can send after this method returns.
        """
        self.closed = True
        self._pending.clear()
        self._last_deadline.clear()
        for sock in self.sockets.values():
            sock.close()
        self.sockets.clear()
        self.flow_ids.clear()
        self._retired_flows.clear()


class ProxyPacketGenerator(_ProxyIO):
    """Listen on localhost and forward received bytes through ``out.put``.

    ``packet_size`` limits a TCP receive; UDP receives always keep whole datagrams.
    Each TCP connection or UDP client address gets a lifetime-unique integer
    flow ID. Call ``close()`` in a finally block after running the environment.
    TCP EOF means full flow closure; TCP half-close is not emulated.
    """

    def __init__(self, env: simpy.Environment, element_id: str, listen_port: int = 3000,
                 packet_size: int = 40960, protocol: str = "tcp",
                 debug: bool = False) -> None:
        self._init_io(env, element_id, packet_size, protocol, debug)
        self.flow_id = 0
        self._packet_id = 0
        self.client_addresses: dict[Hashable, tuple[str, int]] = {}
        kind = socket.SOCK_STREAM if protocol == "tcp" else socket.SOCK_DGRAM
        self.sock = socket.socket(socket.AF_INET, kind)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.settimeout(self.socket_timeout)
            self.sock.bind(("localhost", listen_port))
            if protocol == "tcp":
                self.sock.listen()
        except OSError:
            self.sock.close()
            raise
        self.action = env.process(self.run())

    @property
    def packets_sent(self) -> int:
        return self._packet_id

    def _inputs(self) -> list[socket.socket]:
        return [self.sock] + list(self.sockets.values())

    def on_tcp_accept(self) -> None:
        """Associate a new connection with an ID that cannot alias a prior flow."""
        sock, _ = self.sock.accept()
        sock.settimeout(self.socket_timeout)
        self.flow_id += 1
        self.flow_ids[sock] = self.flow_id
        self.sockets[self.flow_id] = sock

    def on_tcp_close(self, sock: socket.socket) -> None:
        """Close the client and forward an EOF marker to the server-side proxy."""
        self._disconnect(sock)

    def _receive(self, sock: socket.socket) -> None:
        if self.protocol == "tcp" and sock is self.sock:
            self.on_tcp_accept()
            return
        try:
            if self.protocol == "tcp":
                data = sock.recv(self.packet_size)
                if not data:
                    self.on_tcp_close(sock)
                    return
                flow_id = self.flow_ids[sock]
            else:
                data, address = sock.recvfrom(self.udp_receive_size)
                if address not in self.flow_ids:
                    self.flow_id += 1
                    self.flow_ids[address] = self.flow_id
                    self.client_addresses[self.flow_id] = address
                flow_id = self.flow_ids[address]
        except OSError:
            self._disconnect(sock)
            return
        self._emit(flow_id, data)

    def send_to_app(self, packet: Packet) -> None:
        """Deliver a full TCP payload or one UDP datagram to its originating app."""
        if self.closed:
            return
        if self.protocol == "tcp":
            sock = self.sockets.get(packet.flow_id)
            if sock is None:
                return
            if packet.payload is None:
                self._close_flow(packet.flow_id)
                return
            try:
                sock.sendall(packet.payload)
            except OSError:
                self._disconnect(sock)
        elif packet.flow_id in self.client_addresses:
            self.sock.sendto(packet.payload, self.client_addresses[packet.flow_id])

    def put(self, packet: Packet) -> None:
        """Schedule application delivery after its simulated path delay."""
        self._schedule(packet)

    def close(self) -> None:
        super().close()
        self.sock.close()
        self.client_addresses.clear()
