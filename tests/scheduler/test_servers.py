import pytest

from ns.packet.packet import Packet
from ns.scheduler.drr import DRRServer
from ns.scheduler.monitor import ServerMonitor
from ns.scheduler.sp import SPServer
from ns.scheduler.virtual_clock import VirtualClockServer
from ns.scheduler.wfq import WFQServer

simpy = pytest.importorskip("simpy")


class CaptureSink:
    """Collect packets forwarded by a scheduler."""

    def __init__(self, env, auto_ack=False):
        self.env = env
        self.auto_ack = auto_ack
        self.observed = []

    def put(self, packet, upstream_update=None, upstream_store=None):
        record = {
            "time": self.env.now,
            "packet": packet,
            "upstream_update": upstream_update,
            "upstream_store": upstream_store,
        }
        self.observed.append(record)
        if self.auto_ack and upstream_update is not None:
            upstream_update(packet)


class StoreSpy:
    """Minimal object that records when `get` is called."""

    def __init__(self):
        self.get_calls = 0

    def get(self):
        self.get_calls += 1


class ScriptedServer:
    """Drive deterministic queue sizes for ServerMonitor tests."""

    def __init__(self, env, flow_id, script):
        self.env = env
        self.flow_id = flow_id
        self.queue_sizes = {flow_id: 0}
        self.queue_bytes = {flow_id: 0}
        self.current_packet = None
        env.process(self._drive(script))

    def _drive(self, script):
        for entry in script:
            yield self.env.timeout(entry["delay"])
            self.queue_sizes[self.flow_id] = entry["size"]
            self.queue_bytes[self.flow_id] = entry["bytes"]
            self.current_packet = entry["packet"]

    def packet_in_service(self):
        return self.current_packet

    def byte_size(self, queue_id):
        return self.queue_bytes[queue_id]

    def size(self, queue_id):
        return self.queue_sizes[queue_id]

    def all_flows(self):
        return [self.flow_id]


def make_packet(packet_id, flow_id, size=1500, time=0.0):
    return Packet(
        time=time,
        size=size,
        packet_id=packet_id,
        flow_id=flow_id,
        src="src",
        dst="dst",
    )


def enqueue(env, server, packet, delay=0.0, **kwargs):
    def _send():
        yield env.timeout(delay)
        yield server.put(packet, **kwargs)

    env.process(_send())


def test_drr_weighted_round_robin_serves_proportionally():
    env = simpy.Environment()
    server = DRRServer(env, rate=1e9, weights=[1, 2])
    sink = CaptureSink(env)
    server.out = sink

    enqueue(env, server, make_packet(0, flow_id=0))
    enqueue(env, server, make_packet(1, flow_id=1))
    enqueue(env, server, make_packet(2, flow_id=1))

    env.run(until=0.01)
    assert [entry["packet"].flow_id for entry in sink.observed] == [0, 1, 1]


def test_drr_large_packet_served_without_starvation():
    env = simpy.Environment()
    server = DRRServer(env, rate=1e9, weights=[1, 1])
    sink = CaptureSink(env)
    server.out = sink

    enqueue(env, server, make_packet(0, flow_id=0, size=3000))
    enqueue(env, server, make_packet(1, flow_id=1, size=1500))

    env.run(until=0.01)
    assert [entry["packet"].flow_id for entry in sink.observed] == [0, 1]


def test_drr_zero_downstream_buffer_provides_upstream_hooks():
    env = simpy.Environment()
    server = DRRServer(
        env,
        rate=1e9,
        weights={0: 1},
        zero_downstream_buffer=True,
    )
    sink = CaptureSink(env)
    server.out = sink

    enqueue(env, server, make_packet(0, flow_id=0))
    env.run(until=0.01)

    record = sink.observed[0]
    assert record["upstream_update"] == server.update
    assert record["upstream_store"] == server.stores[0]
    assert server.byte_size(0) == 0


def test_drr_updates_quanta_for_large_packets():
    env = simpy.Environment()
    server = DRRServer(env, rate=1e9, weights=[1, 2])
    sink = CaptureSink(env)
    server.out = sink

    enqueue(env, server, make_packet(0, flow_id=0, size=4096))
    enqueue(env, server, make_packet(1, flow_id=1, size=1500))

    env.run(until=0.02)
    assert server.base_quantum >= 4096
    assert server.quantum[0] >= 4096
    assert server.quantum[1] == pytest.approx(server.quantum[0] * 2)


def test_drr_active_queue_tracks_backlogged_flows():
    env = simpy.Environment()
    server = DRRServer(env, rate=1e6, weights=[1, 1, 1])
    sink = CaptureSink(env)
    server.out = sink

    enqueue(env, server, make_packet(0, flow_id=0, size=1000))
    enqueue(env, server, make_packet(1, flow_id=1, size=1000), delay=0.001)

    snapshot = {}

    def probe():
        yield env.timeout(0.0015)
        snapshot["queue"] = list(server.active_queue)
        snapshot["set"] = set(server.active_set)

    env.process(probe())
    env.run(until=0.05)

    assert snapshot["queue"] == [1]
    assert snapshot["set"] == {1}
    assert not server.active_queue
    assert not server.active_set


def test_sp_serves_highest_priority_first():
    env = simpy.Environment()
    priorities = {0: 1, 1: 3}
    server = SPServer(env, rate=1e9, priorities=priorities)
    sink = CaptureSink(env)
    server.out = sink

    enqueue(env, server, make_packet(0, flow_id=0))
    enqueue(env, server, make_packet(1, flow_id=1))

    env.run(until=0.01)
    assert [entry["packet"].flow_id for entry in sink.observed] == [1, 0]


def test_sp_zero_buffer_calls_upstream_callbacks():
    env = simpy.Environment()
    server = SPServer(
        env,
        rate=1e9,
        priorities=[1],
        zero_buffer=True,
    )
    sink = CaptureSink(env)
    server.out = sink

    upstream_store = StoreSpy()
    upstream_invoked = {"count": 0}

    def upstream_update(packet):
        upstream_invoked["count"] += 1
        upstream_invoked["last"] = packet.packet_id

    enqueue(
        env,
        server,
        make_packet(0, flow_id=0),
        upstream_update=upstream_update,
        upstream_store=upstream_store,
    )
    env.run(until=0.01)

    assert upstream_store.get_calls == 1
    assert upstream_invoked["count"] == 1
    assert upstream_invoked["last"] == sink.observed[0]["packet"].packet_id


def test_wfq_orders_by_finish_time_and_resets_virtual_time():
    env = simpy.Environment()
    weights = {0: 1, 1: 2}
    server = WFQServer(env, rate=1e9, weights=weights)
    sink = CaptureSink(env)
    server.out = sink

    # Warm up the scheduler so later packets see a non-empty active set.
    enqueue(env, server, make_packet(0, flow_id=0, size=1000), delay=0.0)

    enqueue(env, server, make_packet(1, flow_id=1, size=1000), delay=1e-6)
    enqueue(env, server, make_packet(2, flow_id=0, size=1000), delay=1.2e-6)
    enqueue(env, server, make_packet(3, flow_id=0, size=1000), delay=1.4e-6)

    env.run(until=0.05)
    observed = [entry["packet"].flow_id for entry in sink.observed]
    assert observed[1:] == [1, 0, 0]
    assert server.vtime == 0.0


def test_wfq_zero_downstream_buffer_and_zero_buffer_callbacks():
    env = simpy.Environment()
    server = WFQServer(
        env,
        rate=1e9,
        weights=[1],
        zero_buffer=True,
        zero_downstream_buffer=True,
    )
    sink = CaptureSink(env, auto_ack=True)
    server.out = sink

    upstream_store = StoreSpy()
    upstream_invoked = {"count": 0}

    def upstream_update(packet):
        upstream_invoked["count"] += 1
        upstream_invoked["last"] = packet.packet_id

    enqueue(
        env,
        server,
        make_packet(0, flow_id=0),
        upstream_update=upstream_update,
        upstream_store=upstream_store,
    )

    env.run(until=0.02)
    assert upstream_store.get_calls == 1
    assert upstream_invoked["count"] == 1
    assert sink.observed[0]["upstream_update"] == server.update


def test_virtual_clock_prefers_smaller_vtick_classes():
    env = simpy.Environment()
    vticks = {0: 2.0, 1: 1.0}
    server = VirtualClockServer(env, rate=1e9, vticks=vticks)
    sink = CaptureSink(env)
    server.out = sink

    enqueue(env, server, make_packet(0, flow_id=0, size=1000))
    enqueue(env, server, make_packet(1, flow_id=1, size=1000))

    env.run(until=0.02)
    assert [entry["packet"].flow_id for entry in sink.observed] == [1, 0]


def test_virtual_clock_zero_downstream_buffer_propagates_callbacks():
    env = simpy.Environment()
    vticks = [1.0]
    server = VirtualClockServer(
        env,
        rate=1e9,
        vticks=vticks,
        zero_downstream_buffer=True,
    )
    sink = CaptureSink(env, auto_ack=True)
    server.out = sink

    enqueue(env, server, make_packet(0, flow_id=0))
    env.run(until=0.02)

    record = sink.observed[0]
    assert record["upstream_update"] == server.update
    assert record["upstream_store"] == server.store


def test_server_monitor_counts_queue_and_service_packets():
    env = simpy.Environment()
    monitored_packet = make_packet(0, flow_id=7, size=200)
    script = [
        {"delay": 0.25, "size": 1, "bytes": 100, "packet": monitored_packet},
        {"delay": 0.5, "size": 0, "bytes": 0, "packet": None},
    ]
    server = ScriptedServer(env, flow_id=7, script=script)
    monitor = ServerMonitor(
        env,
        server,
        dist=lambda: 0.5,
        pkt_in_service_included=True,
    )

    env.run(until=1.1)
    assert monitor.sizes[7] == [2, 0]
    assert monitor.byte_sizes[7] == [300, 0]


def test_server_monitor_ignores_service_when_not_requested():
    env = simpy.Environment()
    monitored_packet = make_packet(0, flow_id=3, size=120)
    script = [
        {"delay": 0.25, "size": 2, "bytes": 256, "packet": monitored_packet},
        {"delay": 0.5, "size": 0, "bytes": 0, "packet": None},
    ]
    server = ScriptedServer(env, flow_id=3, script=script)
    monitor = ServerMonitor(
        env,
        server,
        dist=lambda: 0.5,
        pkt_in_service_included=False,
    )

    env.run(until=1.1)
    assert monitor.sizes[3] == [2, 0]
    assert monitor.byte_sizes[3] == [256, 0]
