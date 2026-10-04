"""Replay genuine CPU feedback and compare explicitly aligned finite TCP flows."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
import simpy

from ns.flow.cc import TCPReno
from ns.flow.cubic import TCPCubic
from ns.flow.flow import Flow
from ns.packet.tcp_generator import TCPPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.port.port import Port
from ns.port.wire import Wire


REFERENCE = Path(__file__).resolve().parents[1] / "reference"
FIXTURE = json.loads((REFERENCE / "days_tcp.json").read_text())
CASES = {case["name"]: case for case in FIXTURE["cases"]}
NS = 1_000_000_000
FLOAT_NS = 0.000001  # One femtosecond; no serialization rounding in shared cases.


def controller(case):
    inputs = case["input"]
    initial = inputs["initial_control"]
    cls = TCPReno if inputs["controller"] == "reno" else TCPCubic
    return cls(mss=inputs["mss_bytes"], cwnd=initial["cwnd_bytes"],
               ssthresh=initial["ssthresh_bytes"])


def assert_control(cc, expected, cubic):
    """Require exact Reno state; bound CUBIC's documented integer rounding."""
    if not cubic:
        assert cc.cwnd == expected["cwnd_bytes"]
        assert cc.ssthresh == expected["ssthresh_bytes"]
        assert cc.ca_credit == expected["ca_credit"]
        return
    # Compare real segment windows against nanosegments, rather than throwing
    # away Python's sub-byte residue. EWMA flooring accumulates less than 8 ns.
    # The elapsed-time friendly curve has derivative alpha*t/rtt**2 in RTT.
    # The friendly branch directly selects this estimate, so its rounding
    # errors do not sum across ACKs. The cubic branch in these short fixtures
    # contracts window error; ten avoidance ACKs accumulate <20 nanosegments
    # of target/ACK-step truncation. Its tiny no-loss curve has a negligible
    # RTT-time derivative (C=0.4 and elapsed+RTT below 10 microseconds).
    # Recovery merely holds/inflates the window; it has no RTT-sensitive growth.
    elapsed_ns = 0 if cc.epoch_start is None else max(
        0, cc.current_time * NS - cc.epoch_start * NS
    )
    rtt_ns = max(1, min(cc.srtt * NS, expected["srtt_ns"]))
    alpha = 3 * (1 - cc.beta) / (1 + cc.beta)
    segment_bound = 2e-8
    if expected["phase"] == 1 and cc.K == 0:
        segment_bound += alpha * elapsed_ns * 8 / rtt_ns**2
    assert segment_bound < 0.01  # Less than 5.12 bytes, never a decision tolerance.
    actual = cc.cwnd / cc.mss
    assert actual == pytest.approx(expected["cwnd_scaled"] / NS,
                                   rel=0, abs=max(1e-8, segment_bound))
    assert cc.ssthresh / cc.mss == pytest.approx(
        expected["ssthresh_scaled"] / NS, rel=0, abs=1e-8
    )
    assert cc.srtt * NS == pytest.approx(expected["srtt_ns"], rel=0, abs=8)
    assert cc.W_max == pytest.approx(expected["w_max_scaled"] / NS,
                                     rel=0, abs=1e-8)
    assert cc.W_last_max == pytest.approx(expected["w_last_max_scaled"] / NS,
                                          rel=0, abs=1e-8)
    if expected["epoch_start_ns"] is None:
        assert cc.epoch_start is None
    else:
        assert cc.epoch_start * NS == pytest.approx(expected["epoch_start_ns"],
                                                   rel=0, abs=FLOAT_NS)
    assert cc.K * NS == pytest.approx(expected["k_ns"], rel=0, abs=1.1)
    assert cc._in_fast_recovery == (expected["phase"] == 2)
    assert cc._in_slow_start == (expected["phase"] == 0)


def replay(case, *, recovery_rtt=True):
    """Apply CPU feedback to public controller hooks, retaining recovery decisions."""
    cc = controller(case)
    cubic = case["input"]["controller"] == "cubic"
    phase = 0
    dupacks = 0
    frontier = 0
    acknowledgment = 0
    for transition in case["output"]["transitions"]:
        before, after = transition["before"], transition["after"]
        assert_control(cc, before, cubic)
        assert (phase, dupacks, frontier) == (
            before["phase"], before["duplicate_acks"],
            before["recovery_high_sequence"],
        )
        feedback = transition["input"]
        now = transition["time_ns"] / NS
        cc.set_before_control(now, feedback["flight_size_bytes"])
        kind = feedback["kind"]
        if kind == "timeout":
            cc.timer_expired()
            phase, dupacks, frontier = 0, 0, 0
        elif kind == "duplicate_ack":
            dupacks += 1
            if dupacks == 3:
                cc.consecutive_dupacks_received()
                phase = 2
                frontier = feedback["recovery_high_sequence"]
            elif dupacks > 3:
                cc.more_dupacks_received()
        else:
            assert kind == "new_ack"
            assert feedback["acknowledgment"] == (
                acknowledgment + feedback["acknowledged_bytes"]
            )
            acknowledgment = feedback["acknowledgment"]
            dupacks = 0
            if phase == 2:
                # CPU echoes attempt RTTs even in recovery. This is a controller
                # equation replay with that explicit input, not a claim that
                # Python's conservative Karn transport supplies fresh samples.
                if cubic and recovery_rtt:
                    cc.ack_received_bytes(feedback["acknowledged_bytes"],
                                          feedback["rtt_sample_ns"] / NS, now)
                if acknowledgment < frontier:
                    cc.partial_ack_received(feedback["acknowledged_bytes"], now)
                else:
                    cc.dupack_over()
                    phase, frontier = 1, 0
            else:
                cc.ack_received_bytes(feedback["acknowledged_bytes"],
                                      feedback["rtt_sample_ns"] / NS, now)
                if phase == 0 and cc.cwnd >= cc.ssthresh:
                    phase = 1
        assert_control(cc, after, cubic)
        assert (phase, dupacks, frontier) == (
            after["phase"], after["duplicate_acks"],
            after["recovery_high_sequence"],
        )
    assert acknowledgment == case["output"]["highest_ack"]


def test_cpu_provenance_and_real_loss_coverage():
    reference = FIXTURE["reference"]
    assert reference["revision"] == "9ff20eac16dcdf752510b05cbcf526684dc05146"
    assert reference["backend"] == "cpu"
    assert reference["workers"] == 2
    assert reference["observation_mode"] == "full"
    assert reference["scalar_equal"] is True
    for filename, key in [("days_tcp.rs", "helper_source_sha256"),
                          ("days_tcp.Cargo.lock", "helper_lock_sha256")]:
        assert hashlib.sha256((REFERENCE / filename).read_bytes()).hexdigest() == (
            reference[key]
        )
    for case in CASES.values():
        output = case["output"]
        assert output["pending_events"] == output["resident_packets"] == 0
        assert output["highest_ack"] == case["input"]["total_bytes"]
        assert output["bytes_in_flight"] == 0
        if case["input"]["bottleneck_loss"]:
            assert output["dropped_packets"] > 0
            assert any(p.get("retransmission") for p in output["packets"])
    assert any(t["input"]["kind"] == "timeout" for t in
               CASES["reno_bottleneck_timeout"]["output"]["transitions"])
    for name in ("reno_bottleneck_loss", "cubic_bottleneck_loss"):
        transitions = CASES[name]["output"]["transitions"]
        assert any(t["before"]["phase"] == 0 and t["after"]["phase"] == 2
                   for t in transitions)
        assert any(t["input"]["kind"] == "new_ack" and
                   t["before"]["phase"] == t["after"]["phase"] == 2
                   for t in transitions)  # a real partial recovery ACK
        assert any(t["before"]["phase"] == 2 and t["after"]["phase"] == 1
                   for t in transitions)


@pytest.mark.parametrize("name", CASES)
def test_controller_replays_actual_cpu_feedback(name):
    replay(CASES[name])


class Recorder:
    """Observe link-local decisions without imposing a global trace order."""

    def __init__(self, env, downstream, ack=False):
        self.env, self.downstream, self.ack = env, downstream, ack
        self.records = []

    def put(self, packet):
        identity = packet.ack if self.ack else packet.packet_id
        self.records.append((identity, packet.size, self.env.now * NS))
        return self.downstream.put(packet)


def expected_records(case, records, kind):
    packets = {p["packet_id"]: p for p in case["output"]["packets"]}
    field = "acknowledgment" if kind == "ack" else "sequence"
    return [(packets[r["packet_id"]][field], packets[r["packet_id"]]["size_bytes"],
             r["time_ns"]) for r in records if packets[r["packet_id"]]["kind"] == kind]


def assert_records(actual, expected):
    assert [r[:2] for r in actual] == [r[:2] for r in expected]
    assert [r[2] for r in actual] == pytest.approx(
        [r[2] for r in expected], rel=0, abs=FLOAT_NS
    )


@pytest.mark.parametrize("name", ["reno_growth_short_tail", "reno_avoidance",
                                 "cubic_growth_short_tail", "cubic_avoidance"])
def test_aligned_end_to_end_packet_departures_and_acks(name):
    case = CASES[name]
    inputs, expected = case["input"], case["output"]
    env = simpy.Environment()
    cc = controller(case)
    sender = TCPPacketGenerator(env, Flow(0, "source", "sink",
                                          size=inputs["total_bytes"], start_time=0), cc)
    receiver = TCPSink(env)
    forward = Port(env, rate=inputs["rate_bps"])
    reverse = Port(env, rate=inputs["rate_bps"])
    forward_wire = Wire(env, delay_dist=lambda: inputs["propagation_ns"] / NS)
    reverse_wire = Wire(env, delay_dist=lambda: inputs["propagation_ns"] / NS)
    data_arrivals = Recorder(env, receiver)
    ack_arrivals = Recorder(env, sender, ack=True)
    data_departures = Recorder(env, forward_wire)
    ack_departures = Recorder(env, reverse_wire, ack=True)
    sender.out, receiver.out = forward, reverse
    forward.out, reverse.out = data_departures, ack_departures
    forward_wire.out, reverse_wire.out = data_arrivals, ack_arrivals
    # Stop beyond finite completion; stopped Timer processes may retain a wakeup
    # until their old deadline. Only observations through Days' horizon compare.
    env.run(until=inputs["stop_time_ns"] / NS)
    assert_records(data_departures.records,
                   expected_records(case, expected["departures"], "data"))
    assert_records(ack_departures.records,
                   expected_records(case, expected["departures"], "ack"))
    assert_records(data_arrivals.records, expected_records(case, [
        r for r in expected["arrivals"] if r["disposition"] == "delivered"], "data"))
    assert_records(ack_arrivals.records, expected_records(case, [
        r for r in expected["arrivals"] if r["disposition"] == "feedback"], "ack"))
    assert receiver.bytes_delivered == sender.last_ack == inputs["total_bytes"]
    assert sender.bytes_in_flight == 0
    assert not sender.segment_state and not sender.timers
    assert len(ack_arrivals.records) == expected["feedback_packets"] == 13
    assert data_arrivals.records[-1][1] == 123


@pytest.mark.parametrize("name", ["reno_avoidance", "cubic_avoidance"])
def test_reference_comparator_rejects_one_mss_transition_change(name):
    changed = deepcopy(CASES[name])
    after = changed["output"]["transitions"][0]["after"]
    after["cwnd_bytes"] += 512
    after["cwnd_scaled"] += NS
    with pytest.raises(AssertionError):
        replay(changed)


@pytest.mark.parametrize("mutation", ["identity", "one_nanosecond"])
def test_reference_comparator_rejects_departure_change(monkeypatch, mutation):
    name = "reno_growth_short_tail"
    changed = deepcopy(CASES[name])
    if mutation == "identity":
        changed["output"]["packets"][0]["sequence"] += 512
    else:
        changed["output"]["departures"][0]["time_ns"] += 1
    monkeypatch.setitem(CASES, name, changed)
    with pytest.raises(AssertionError):
        test_aligned_end_to_end_packet_departures_and_acks(name)


def test_cubic_recovery_rtt_difference_is_not_hidden_by_tolerance():
    # Model the Python transport's conservative recovery hooks: no fresh RTT.
    # CPU's echoed-attempt samples change SRTT on the first partial recovery ACK.
    # Consequently full post-loss CUBIC transport equivalence is not claimed.
    with pytest.raises(AssertionError):
        replay(CASES["cubic_bottleneck_loss"], recovery_rtt=False)
