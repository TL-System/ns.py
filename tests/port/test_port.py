import pytest
import simpy

from ns.packet.packet import Packet
from ns.port.monitor import PortMonitor
from ns.port.port import Port


class CaptureSink:
    def __init__(self, env):
        self.env = env
        self.received = []

    def put(self, packet):
        self.received.append((self.env.now, packet))


class RetainingSink:
    """Release a retained upstream packet only when the test asks for it."""

    def __init__(self):
        self.received = []

    def put(self, packet, upstream_update, upstream_store):
        self.received.append((packet, upstream_update, upstream_store))

    def release(self):
        packet, update, store = self.received.pop(0)
        assert store.get().value is packet
        update(packet)


def make_port(env, rate=800, **kwargs):
    port = Port(env, rate, **kwargs)
    port.out = CaptureSink(env)
    return port


@pytest.mark.parametrize("limit_bytes,qlimit", [(False, 1), (True, 100)])
def test_exact_capacity_accepts_first_packet_and_rejects_overflow(limit_bytes, qlimit):
    env = simpy.Environment()
    port = make_port(env, qlimit=qlimit, limit_bytes=limit_bytes)
    accepted = Packet(0, 100, 1)
    dropped = Packet(0, 1, 2)

    assert port.put(accepted) is not None
    assert port.put(dropped) is None
    env.run()

    assert port.out.received == [(1, accepted)]
    assert (port.packets_received, port.packets_dropped, port.byte_size) == (2, 1, 0)


@pytest.mark.parametrize("limit_bytes,qlimit", [(False, 2), (True, 200)])
def test_capacity_counts_service_until_departure(limit_bytes, qlimit):
    env = simpy.Environment()
    port = make_port(env, qlimit=qlimit, limit_bytes=limit_bytes)
    packets = [Packet(0, 100, i) for i in range(4)]
    port.put(packets[0])
    env.run(until=0.25)
    assert port.put(packets[1]) is not None
    assert port.put(packets[2]) is None
    env.run(until=1.25)
    assert port.put(packets[3]) is not None
    env.run()

    assert port.out.received == [(1, packets[0]), (2, packets[1]), (3, packets[3])]
    assert port.byte_size == 0
    assert port.packets_dropped == 1


def test_pending_store_get_does_not_bypass_packet_capacity():
    env = simpy.Environment()
    port = make_port(env, qlimit=1)
    env.run(until=0.25)  # The idle process is now blocked on Store.get().
    first = Packet(env.now, 100, 1)
    second = Packet(env.now, 100, 2)

    assert port.put(first) is not None
    assert port.put(second) is None
    env.run()

    assert port.out.received == [(1.25, first)]


def test_unlimited_rate_drains_bytes_and_preserves_identity_order():
    env = simpy.Environment()
    port = make_port(env, rate=0)
    packets = [Packet(0, size, i) for i, size in enumerate([100, 40, 150])]
    for packet in packets:
        port.put(packet)
    env.run()

    assert port.out.received == [(0, packet) for packet in packets]
    assert port.byte_size == 0
    assert port.busy == port.busy_packet_size == 0
    assert not port.store.items


@pytest.mark.parametrize("zero_downstream_buffer", [False, True])
def test_monitor_distinguishes_queue_from_local_service(zero_downstream_buffer):
    env = simpy.Environment()
    port = make_port(env, zero_downstream_buffer=zero_downstream_buffer)
    if zero_downstream_buffer:
        port.out = RetainingSink()
    waiting = PortMonitor(env, port, lambda: 0.5)
    total = PortMonitor(env, port, lambda: 0.5, pkt_in_service_included=True)
    port.put(Packet(0, 100, 1))
    port.put(Packet(0, 40, 2))
    env.run(until=0.75)

    assert waiting.sizes == [1]
    assert waiting.sizes_byte == [40]
    assert total.sizes == [2]
    assert total.sizes_byte == [140]


@pytest.mark.parametrize("rate", [0, 800])
def test_downstream_backpressure_retains_capacity_until_callback(rate):
    env = simpy.Environment()
    port = make_port(env, rate=rate, qlimit=1, zero_downstream_buffer=True)
    retained = RetainingSink()
    port.out = retained
    first = Packet(0, 100, 1)
    port.put(first)
    env.run()

    assert port.byte_size == 100
    assert port.store.items == [first]
    assert port.put(Packet(env.now, 40, 2)) is None
    retained.release()
    assert port.byte_size == 0  # Account on release, without another put().
    last = Packet(env.now, 40, 3)
    assert port.put(last) is not None
    env.run()
    retained.release()
    assert not port.store.items
    assert port.byte_size == 0
    assert port.packets_received == 3
    assert port.packets_dropped == 1


def test_fifo_mixed_sizes_serializes_in_bits_and_records_hop_entry():
    env = simpy.Environment()
    port = make_port(env, rate=800, element_id="egress")
    packets = [Packet(0, size, i) for i, size in enumerate([100, 40, 150])]
    for packet in packets:
        port.put(packet)
    env.run()

    assert [packet for _, packet in port.out.received] == packets
    assert [time for time, _ in port.out.received] == pytest.approx([1, 1.4, 2.9])
    assert all(packet.perhop_time == {"egress": 0} for packet in packets)
    assert port.byte_size == 0


def test_delayed_downstream_release_does_not_release_next_local_service():
    env = simpy.Environment()
    port = make_port(env, zero_downstream_buffer=True, qlimit=200, limit_bytes=True)
    retained = RetainingSink()
    port.out = retained
    first = Packet(0, 100, 1)
    next_packet = Packet(0, 100, 2)
    port.put(first)
    port.put(next_packet)
    env.run(until=1.25)

    assert port.busy_packet_size == 100
    assert port.byte_size == 200
    retained.release()
    assert port.busy_packet_size == 100
    assert port.byte_size == 100
    assert port.put(Packet(env.now, 100, 3)) is not None
    assert port.put(Packet(env.now, 1, 4)) is None
    env.run()
    retained.release()
    retained.release()
    assert port.byte_size == 0
    assert port.packets_received == 4
    assert port.packets_dropped == 1


def test_monitor_counts_retained_packet_after_local_service_and_release():
    env = simpy.Environment()
    port = make_port(env, zero_downstream_buffer=True)
    retained = RetainingSink()
    port.out = retained
    waiting = PortMonitor(env, port, lambda: 0.5)
    total = PortMonitor(env, port, lambda: 0.5, pkt_in_service_included=True)
    port.put(Packet(0, 100, 1))
    env.run(until=1.25)

    assert waiting.sizes == [0, 1]
    assert waiting.sizes_byte == [0, 100]
    assert total.sizes == [1, 1]
    assert total.sizes_byte == [100, 100]
    retained.release()
    env.run(until=1.75)
    assert waiting.sizes[-1] == total.sizes[-1] == 0
    assert waiting.sizes_byte[-1] == total.sizes_byte[-1] == 0


@pytest.mark.parametrize("limit_bytes", [False, True])
def test_zero_capacity_rejects_packets(limit_bytes):
    env = simpy.Environment()
    port = make_port(env, qlimit=0, limit_bytes=limit_bytes)
    assert port.put(Packet(0, 100, 1)) is None
    env.run()
    assert port.out.received == []
    assert port.byte_size == 0
    assert port.packets_dropped == 1
