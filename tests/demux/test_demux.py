"""Route selection must forward once or account for an unroutable packet."""

import pytest
import simpy

from ns.demux.fib_demux import FIBDemux
from ns.demux.flow_demux import FlowDemux
from ns.demux.random_demux import RandomDemux
from ns.packet.packet import Packet


class Capture:
    def __init__(self):
        self.packets = []

    def put(self, packet):
        self.packets.append(packet)


@pytest.mark.parametrize("flow_id", [-1, 2, "class", None])
@pytest.mark.parametrize("fallback", [False, True])
def test_flow_demux_unknown_ids_use_default_or_drop(flow_id, fallback):
    outs = [Capture(), Capture()]
    default = Capture() if fallback else None
    demux = FlowDemux(outs, default)
    packet = Packet(0, 100, 0, flow_id=flow_id)
    demux.put(packet)
    assert all(not out.packets for out in outs)
    assert demux.packets_received == 1
    assert demux.packets_dropped == (0 if fallback else 1)
    if fallback:
        assert default.packets == [packet]


def test_flow_demux_valid_indexes_preserve_identity_and_order():
    outs = [Capture(), Capture()]
    demux = FlowDemux(outs)
    packets = [Packet(0, 100, i, flow_id=i % 2) for i in range(4)]
    for packet in packets:
        demux.put(packet)
    assert outs[0].packets == packets[::2]
    assert outs[1].packets == packets[1::2]
    assert demux.packets_dropped == 0


@pytest.mark.parametrize("route", [None, {}, {"data": -1}, {"data": 2}, {"data": "x"}])
@pytest.mark.parametrize("fallback", [False, True])
def test_fib_demux_missing_or_invalid_route_is_accounted(route, fallback):
    outs = [Capture(), Capture()]
    default = Capture() if fallback else None
    demux = FIBDemux(route, outs, default=default)
    packet = Packet(0, 100, 0, flow_id="data")
    demux.put(packet)
    assert all(not out.packets for out in outs)
    assert demux.packets_dropped == (0 if fallback else 1)
    if fallback:
        assert default.packets == [packet]


def test_fib_terminal_delivery_precedes_route_and_preserves_mapping():
    output, endpoint = Capture(), Capture()
    ends = {"data": endpoint}
    demux = FIBDemux({"data": 0}, [output], ends)
    packet = Packet(0, 100, 0, flow_id="data")
    demux.put(packet)
    assert endpoint.packets == [packet]
    assert not output.packets
    assert demux.packets_dropped == 0
    # An initially empty endpoint map can also be populated by the caller.
    empty = {}
    demux = FIBDemux(ends=empty)
    empty["data"] = endpoint
    demux.put(packet)
    assert endpoint.packets == [packet, packet]


def test_fib_does_not_retry_a_downstream_exception_through_default():
    class Rejecting(Capture):
        def put(self, packet):
            super().put(packet)
            raise ValueError("downstream failure")

    output, default = Rejecting(), Capture()
    demux = FIBDemux({0: 0}, [output], default=default)
    packet = Packet(0, 100, 0)
    with pytest.raises(ValueError, match="downstream failure"):
        demux.put(packet)
    assert output.packets == [packet]
    assert not default.packets


@pytest.mark.parametrize("kind", ["fib", "flow"])
def test_disconnected_demux_output_is_dropped(kind):
    demux = FIBDemux({0: 0}, [None]) if kind == "fib" else FlowDemux([None])
    demux.put(Packet(0, 100, 0))
    assert demux.packets_dropped == 1


@pytest.mark.parametrize(
    "weights", [[], [0, 0], [-1, 2], [float("nan"), 1], [float("inf"), 1]]
)
def test_random_demux_rejects_invalid_probability_weights(weights):
    with pytest.raises(ValueError, match="weights"):
        RandomDemux(simpy.Environment(), weights)


def test_random_demux_zero_weight_and_disconnected_output():
    weights = [0, 2]
    demux = RandomDemux(simpy.Environment(), weights)
    zero, selected = Capture(), Capture()
    demux.outs = [zero, selected]
    # The constructor owns its weight list; caller mutation cannot change routes.
    weights[:] = [2, 0]
    packet = Packet(0, 100, 0)
    for _ in range(4):
        demux.put(packet)
    assert selected.packets == [packet] * 4
    assert not zero.packets
    demux.outs[1] = None
    demux.put(packet)
    assert demux.packets_received == 5
    assert demux.packets_dropped == 1
