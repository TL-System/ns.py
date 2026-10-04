"""Bounded local sockets exercise proxy payloads, flow identity, and shutdown."""

import socket
import time
from select import select

import pytest
import simpy

from ns.packet.packet import Packet
from ns.packet.proxy_generator import ProxyPacketGenerator
from ns.packet.proxy_sink import ProxySink


class Collector:
    def __init__(self):
        self.packets = []

    def put(self, packet):
        self.packets.append(packet)


def drive(env, condition, seconds=1):
    """Step only until the observation arrives, with a wall-clock deadline."""
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        env.step()
    assert condition(), "Loopback observation did not arrive before the deadline"


def cleanup(proxy):
    # This fallback lets the failing baseline tests release their real sockets.
    if hasattr(proxy, "close"):
        proxy.close()
    else:
        for sock in list(proxy.sockets.values()):
            sock.close()
        for name in ("sock", "udpserver_sock"):
            sock = getattr(proxy, name, None)
            if sock is not None:
                sock.close()


@pytest.mark.parametrize("protocol", ["tcp", "udp"])
def test_generator_measures_payload_and_distinguishes_udp_empty(protocol):
    env = simpy.Environment()
    generator = ProxyPacketGenerator(env, "source", 0, protocol=protocol)
    collector = Collector()
    generator.out = collector
    kind = socket.SOCK_STREAM if protocol == "tcp" else socket.SOCK_DGRAM
    with socket.socket(socket.AF_INET, kind) as client:
        client.settimeout(1)
        try:
            client.connect(generator.sock.getsockname())
            client.sendall(b"hello")
            drive(env, lambda: len(collector.packets) == 1)
            assert collector.packets[0].size == 5
            assert collector.packets[0].payload == b"hello"
            if protocol == "udp":
                client.send(b"")
                drive(env, lambda: len(collector.packets) == 2)
                assert collector.packets[1].payload == b""
            else:
                client.shutdown(socket.SHUT_WR)
                drive(env, lambda: len(collector.packets) == 2)
                assert collector.packets[1].payload is None
            assert [packet.packet_id for packet in collector.packets] == [1, 2]
        finally:
            cleanup(generator)


def test_udp_clients_get_their_own_return_datagrams():
    env = simpy.Environment()
    generator = ProxyPacketGenerator(env, "source", 0, protocol="udp")
    collector = Collector()
    generator.out = collector
    clients = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(2)]
    try:
        for client, data in zip(clients, [b"first", b"second"]):
            client.settimeout(1)
            client.connect(generator.sock.getsockname())
            client.send(data)
        drive(env, lambda: len(collector.packets) == 2)
        assert len({packet.flow_id for packet in collector.packets}) == 2
        for packet in reversed(collector.packets):
            generator.put(packet)
        drive(env, lambda: len(select(clients, [], [], 0)[0]) == 2)
        assert [client.recv(100) for client in clients] == [b"first", b"second"]
    finally:
        for client in clients:
            client.close()
        cleanup(generator)


def test_udp_sink_keeps_flow_identity_including_empty_datagram():
    env = simpy.Environment()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind(("127.0.0.1", 0))
        server.settimeout(1)
        sink = ProxySink(env, "sink", server.getsockname(), protocol="udp")
        collector = Collector()
        sink.out = collector
        try:
            for flow, payload in [(11, b"first"), (22, b"")]:
                sink.put(Packet(env.now, len(payload), flow, flow_id=flow,
                                payload=payload))
            requests = [server.recvfrom(100) for _ in range(2)]
            assert requests[0][1] != requests[1][1]
            for payload, address in reversed(requests):
                server.sendto(payload, address)
            drive(env, lambda: len(collector.packets) == 2)
            assert {(p.flow_id, p.payload, p.size) for p in collector.packets} == {
                (11, b"first", 5), (22, b"", 0)
            }
        finally:
            cleanup(sink)


def test_tcp_sink_closes_connection_on_close_marker_and_counts_bytes():
    env = simpy.Environment()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        server.settimeout(1)
        sink = ProxySink(env, "sink", server.getsockname(), rec_waits=True,
                         rec_flow_ids=True)
        try:
            packet = Packet(0, 5, 1, flow_id=8, payload=b"hello")
            packet.perhop_time["wire"] = 0
            sink.put(packet)
            with server.accept()[0] as connection:
                connection.settimeout(1)
                assert connection.recv(100) == b"hello"
                packet.perhop_time["wire"] = 100
                assert sink.perhop_times[8] == [{"wire": 0}]
                assert sink.bytes_received[8] == 5
                sink.put(Packet(env.now, 0, 2, flow_id=8, payload=None))
                assert connection.recv(100) == b""
                assert sink.packets_received[8] == 1
        finally:
            cleanup(sink)


@pytest.mark.parametrize("proxy_type", [ProxyPacketGenerator, ProxySink])
def test_polling_yields_when_simulation_starts_ahead_of_wall_clock(proxy_type):
    env = simpy.Environment(initial_time=10)
    proxy = (ProxyPacketGenerator(env, "source", 0) if
             proxy_type is ProxyPacketGenerator else
             ProxySink(env, "sink", ("127.0.0.1", 1)))
    try:
        env.run(until=10.02)
        assert env.now == 10.02
    finally:
        cleanup(proxy)


@pytest.mark.parametrize("proxy_type", [ProxyPacketGenerator, ProxySink])
def test_tcp_partial_writes_deliver_all_bytes(proxy_type):
    class PartialTransport:
        """A socket-like stream where a single send accepts only one byte."""
        def __init__(self):
            self.received = b""

        def send(self, data):
            self.received += data[:1]
            return min(len(data), 1)

        def sendall(self, data):
            self.received += data

        def close(self):
            pass

    env = simpy.Environment()
    proxy = (ProxyPacketGenerator(env, "source", 0) if
             proxy_type is ProxyPacketGenerator else
             ProxySink(env, "sink", ("127.0.0.1", 1)))
    transport = PartialTransport()
    proxy.sockets[7] = transport
    proxy.flow_ids[transport] = 7
    try:
        proxy.put(Packet(0, 9, 1, flow_id=7, payload=b"all bytes"))
        assert transport.received == b"all bytes"
    finally:
        cleanup(proxy)


def test_tcp_sink_returns_payloads_and_eof_for_each_connection():
    env = simpy.Environment()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        server.settimeout(1)
        sink = ProxySink(env, "sink", server.getsockname(), packet_size=3)
        collector = Collector()
        sink.out = collector
        connections = []
        try:
            for flow, payload in [(11, b"one"), (22, b"two")]:
                sink.put(Packet(0, len(payload), flow, flow_id=flow, payload=payload))
                connection = server.accept()[0]
                connections.append(connection)
                connection.settimeout(1)
                assert connection.recv(100) == payload
                connection.sendall(payload + b" reply")
                connection.shutdown(socket.SHUT_WR)
            drive(env, lambda: sum(p.payload is None for p in collector.packets) == 2)
            for flow, expected in [(11, b"one reply"), (22, b"two reply")]:
                assert b"".join(p.payload for p in collector.packets
                                if p.flow_id == flow and p.payload is not None) == expected
                assert sum(p.size for p in collector.packets
                           if p.flow_id == flow) == len(expected)
            assert len({p.packet_id for p in collector.packets}) == len(collector.packets)
            assert not sink.sockets
        finally:
            for connection in connections:
                connection.close()
            cleanup(sink)


@pytest.mark.parametrize("proxy_type", [ProxyPacketGenerator, ProxySink])
def test_delayed_data_precedes_eof_and_explicit_close_cancels_work(
    proxy_type, monkeypatch,
):
    from types import SimpleNamespace
    import ns.packet.proxy_generator as proxy_module

    clock = [100.0]
    monkeypatch.setattr(proxy_module, "time", SimpleNamespace(
        monotonic=lambda: clock[0], sleep=lambda _: None,
    ))
    monkeypatch.setattr(proxy_module, "select", lambda *args: ([], [], []))
    env = simpy.Environment(initial_time=10)
    proxy = (ProxyPacketGenerator(env, "source", 0) if
             proxy_type is ProxyPacketGenerator else
             ProxySink(env, "sink", ("127.0.0.1", 1)))
    left, right = socket.socketpair()
    right.settimeout(1)
    proxy.sockets[7] = left
    proxy.flow_ids[left] = 7
    try:
        proxy.put(Packet(9, 5, 1, realtime=100, flow_id=7, payload=b"later"))
        # Even though EOF is already due, it must follow the accepted data.
        proxy.put(Packet(10, 0, 2, realtime=100, flow_id=7, payload=None))
        env.step()  # Start polling before moving the injected wall clock.
        clock[0] = 100.9
        env.step()
        assert not select([right], [], [], 0)[0]
        clock[0] = 101
        env.step()
        assert right.recv(100) == b"later"
        assert right.recv(100) == b""
        proxy.put(Packet(9, 6, 3, realtime=102, flow_id=8, payload=b"cancel"))
        proxy.close()
        proxy.close()
        clock[0] = 200
        env.run(until=env.now + 1)
        assert proxy.action.triggered
        assert not proxy.sockets
        # Putting after close must not connect to the unavailable destination.
        proxy.put(Packet(env.now, 5, 4, flow_id=8, payload=b"after"))
    finally:
        left.close()
        right.close()
        cleanup(proxy)


def test_remove_closed_sockets_retires_every_flow():
    env = simpy.Environment()
    generator = ProxyPacketGenerator(env, "source", 0)
    collector = Collector()
    generator.out = collector
    try:
        for flow in [7, 8]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            generator.flow_ids[sock] = flow
            generator.sockets[flow] = sock
            sock.close()
        generator.remove_closed_sockets()
        assert not generator.sockets
        assert not generator.flow_ids
        assert {p.flow_id for p in collector.packets} == {7, 8}
    finally:
        cleanup(generator)


@pytest.mark.parametrize("proxy_type", [ProxyPacketGenerator, ProxySink])
def test_udp_preserves_datagram_larger_than_tcp_receive_limit(proxy_type):
    env = simpy.Environment()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as peer:
        peer.bind(("127.0.0.1", 0))
        peer.settimeout(1)
        proxy = (ProxyPacketGenerator(env, "source", 0, packet_size=3,
                                      protocol="udp") if
                 proxy_type is ProxyPacketGenerator else
                 ProxySink(env, "sink", peer.getsockname(), packet_size=3,
                           protocol="udp"))
        collector = Collector()
        proxy.out = collector
        try:
            if proxy_type is ProxyPacketGenerator:
                peer.sendto(b"whole datagram", proxy.sock.getsockname())
            else:
                proxy.put(Packet(0, 1, 1, flow_id=7, payload=b"x"))
                _, address = peer.recvfrom(100)
                peer.sendto(b"whole datagram", address)
            drive(env, lambda: len(collector.packets) == 1)
            assert collector.packets[0].payload == b"whole datagram"
            assert collector.packets[0].size == 14
        finally:
            cleanup(proxy)


@pytest.mark.parametrize("error", [ConnectionRefusedError, socket.timeout])
def test_failed_connect_closes_the_new_socket(monkeypatch, error):
    import ns.packet.proxy_sink as sink_module

    env = simpy.Environment()
    sink = ProxySink(env, "sink", ("127.0.0.1", 1))
    original_socket = socket.socket
    opened = []

    class FailedConnection(original_socket):
        """A real descriptor with a deterministic connection failure."""
        def connect(self, destination):
            raise error("Injected connect failure")

    def tracked_socket(*args, **kwargs):
        sock = FailedConnection(*args, **kwargs)
        opened.append(sock)
        return sock

    monkeypatch.setattr(sink_module.socket, "socket", tracked_socket)
    try:
        with pytest.raises(error):
            sink.put(Packet(0, 5, 1, flow_id=7, payload=b"hello"))
        assert len(opened) == 1
        assert opened[0].fileno() == -1
        assert not sink.sockets
    finally:
        for sock in opened:
            sock.close()
        cleanup(sink)


@pytest.mark.parametrize("proxy_type", [ProxyPacketGenerator, ProxySink])
def test_tcp_failed_write_terminates_flow_without_replaying_prefix(proxy_type):
    class FailedWrite:
        def __init__(self, sock):
            self.sock = sock

        def sendall(self, payload):
            self.sock.sendall(payload[:1])
            raise socket.timeout("Injected timeout after a partial write")

        def close(self):
            self.sock.close()

    env = simpy.Environment()
    proxy = (ProxyPacketGenerator(env, "source", 0) if
             proxy_type is ProxyPacketGenerator else
             ProxySink(env, "sink", ("127.0.0.1", 1)))
    collector = Collector()
    proxy.out = collector
    left, right = socket.socketpair()
    right.settimeout(1)
    stream = FailedWrite(left)
    proxy.sockets[7] = stream
    proxy.flow_ids[stream] = 7
    try:
        proxy.put(Packet(0, 9, 1, flow_id=7, payload=b"all bytes"))
        assert right.recv(100) == b"a"
        assert right.recv(100) == b""
        assert [(p.flow_id, p.payload) for p in collector.packets] == [(7, None)]
        assert not proxy.sockets
    finally:
        left.close()
        right.close()
        cleanup(proxy)


@pytest.mark.parametrize("close_path", ["server_eof", "close_marker", "send_error"])
def test_tcp_retired_flow_does_not_open_a_second_server_connection(
    close_path, monkeypatch,
):
    env = simpy.Environment()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        server.settimeout(1)
        if close_path == "send_error":
            class FailedSend(socket.socket):
                def sendall(self, payload):
                    if payload == b"fail":
                        raise socket.timeout("Injected write failure")
                    return super().sendall(payload)

            monkeypatch.setattr(socket, "socket", FailedSend)
        sink = ProxySink(env, "sink", server.getsockname())
        collector = Collector()
        sink.out = collector
        try:
            sink.put(Packet(0, 5, 1, flow_id=7, payload=b"first"))
            with server.accept()[0] as connection:
                connection.settimeout(1)
                assert connection.recv(100) == b"first"
                if close_path == "close_marker":
                    sink.put(Packet(env.now, 0, 2, flow_id=7, payload=None))
                    assert connection.recv(100) == b""
                elif close_path == "send_error":
                    sink.put(Packet(env.now, 4, 2, flow_id=7, payload=b"fail"))
                    assert connection.recv(100) == b""
            if close_path == "server_eof":
                drive(env, lambda: any(p.payload is None for p in collector.packets))
                assert [(p.flow_id, p.payload) for p in collector.packets] == [(7, None)]
            # A request already in the simulated path can arrive after real EOF.
            sink.put(Packet(env.now, 4, 3, flow_id=7, payload=b"late"))
            assert not select([server], [], [], 0.03)[0], "Closed TCP flow reopened"
        finally:
            cleanup(sink)
