# Phase 4: classic TCP sender mechanics

Implemented against accepted Phase 3 `9659756` on 2026-10-03. The inspected Days
reference is `9ff20eac16dcdf752510b05cbcf526684dc05146`. This task owns
`ns/packet/tcp_generator.py`, `tests/packet/test_tcp_generator.py`, and
`tests/packet/test_tcp_transport.py`. The coordinator explicitly authorized the
small `CongestionControl.partial_ack_received()` base hook in `ns/flow/cc.py`;
its default is a documented no-op, with controller response deferred to Phase 5.
The coordinator records the candidate commit and runs fresh review/integration.

## Byte and lifecycle contract

Data sequences, flow sizes, the application buffer frontier, and emitted sizes
are integral bytes. MSS follows the controller's `mss`, falling back to 512 for
older custom controllers without that attribute. Positive continuous
`size_dist()` results are floored once per application burst. Nonfinite,
negative, zero, and subbyte bursts are rejected, preventing zero-time source
livelock. An explicit finite flow size caps every burst, including a burst larger
than the entire flow. Fractional congestion-window credit is retained in the
controller but only its whole-byte allowance can become data. Short final
segments and window-limited segments are legal.

Application arrivals retain an absolute clock anchored when the sender starts;
a window stall can leave past arrivals available without an additional delay.
No separate application engine was added. `start_time` is absolute simulation
time rather than an extra delay from an already advanced environment.
`finish_time` is an exclusive new-data transmission deadline; it wakes a
window-blocked generator and excludes arrivals at or beyond the boundary.
Already emitted data remains reliable and may be retransmitted/ACKed afterward.
An omitted finish time is unbounded. This deadline is distinct from an
`env.run(until=...)` observation cutoff, which can leave a flow incompletely
drained. A finite size finishes new-data generation as soon as all bytes are
emitted; reliability ends only when those bytes are cumulatively acknowledged.

`bytes_in_flight` is `next_seq - last_ack`: each unique outstanding byte counts
once, independent of retransmission attempts. Logical segment state is
sender-owned. Every physical retransmission is a fresh `Packet`, retaining the
original first-transmit `Packet.time` for sink latency. A partial ACK retires its
prefix and retains only the outstanding suffix; it never mutates a downstream
packet. `sent_packets` remains an inspection mapping of outstanding range starts
to their latest physical attempt, which can still include an ACKed prefix.
The state map, rather than mutable packet fields, governs recovery and timing.

A send registers the outstanding range, advances `next_seq`, and arms its timer
before forwarding to `out.put()`. Retransmission updates attempt metadata and
rearms the timer before forwarding. Thus an immediate synchronous ACK sees a
complete transport transition and can cancel its timer, including an ACK during
a timeout callback. Window notifications are coalesced and the sequential SimPy
process always rechecks actual byte credit.

## ACKs and recovery

Only ACK flow ID `flow.fid + 10000` is accepted. Negative, nonintegral, Boolean,
stale, future, wrong-flow, and no-outstanding-data ACKs cannot modify sender or
controller state. A cumulative ACK retires exactly the covered bytes, including
complete intermediate ranges and an optional partial suffix. Old or repeated
ACKs after completion cannot revive retransmission or trigger congestion loss.

Fast retransmit occurs once, on the third duplicate ACK. Its recovery frontier
is the highest byte already sent at that moment. Later duplicate ACKs notify the
controller and wake new-data transmission when the resulting window permits it;
they do not repeatedly retransmit the same hole. An ACK before that recovery
frontier retransmits the next missing range and calls
`partial_ack_received(acknowledged_bytes, current_time)` while remaining in
recovery. Even the first duplicate ACK after a partial ACK grants recovery credit
without a second loss reduction. Only an ACK covering the recovery frontier
calls `dupack_over()`. That exit ACK does not also perform ordinary ACK growth.
An ACK after just one or two duplicates is ordinary feedback, not recovery exit.

The existing `set_before_control(now, bytes_in_flight)` hook supplies the flight
size before classic feedback removes newly ACKed bytes, matching the information
needed by Days's control transitions. Builtin Reno/CUBIC's flight-based loss
threshold, acknowledged-byte growth, and partial-recovery window adjustment
remain Phase 5 work; the Phase 4 base partial-ACK hook intentionally leaves the
controller window unchanged. Transport tests use an explicit recording
controller to establish transitions independently of those pending algorithms.

## Timer and RTT

There is one timer for the oldest outstanding byte range. The public `timers`
mapping is retained as a compatibility view containing at most that one timer.
Sending later data does not restart it. Advancing ACKs restart from ACK reception
using the current connection RTO; fast retransmit and partial recovery likewise
rearm before emitting their fresh attempts. Expiration retransmits only the
oldest unacknowledged range and doubles the connection's RTO. The backed-off
value applies to subsequent data as well. Complete acknowledgement empties all
outstanding maps and stops the timer; stale callbacks are harmless.

RTT sampling follows the conservative timing contract in `docs/tcp_timing.md`:
only an ACK covering exactly one complete, never-retransmitted, never-trimmed
range is eligible. Cumulative, retransmitted, and partial-range ACKs do not
supply a guessed sample; ACK packet timestamps are not authoritative. SRTT and
RTTVAR have an explicit initialization flag, so a real zero RTT does not reset
the estimator on its next sample. Variance uses the previous SRTT. Learned RTO
uses a one-second minimum, 60-second maximum, and 1 ms variation granularity;
backoff also caps at 60 seconds. RTT and simulation time retain floating-point
seconds rather than being quantized to Days's integer nanoseconds.

These choices follow [RFC 6298](https://www.rfc-editor.org/rfc/rfc6298.html)
sections 2, 3, and 5. Recovery sequencing uses the distinction between partial
and full recovery ACKs in
[RFC 6582](https://www.rfc-editor.org/rfc/rfc6582.html) section 3; Days's
simplified partial-window formula remains a controller-phase concern. Duplicate
ACK credit follows [RFC 5681](https://www.rfc-editor.org/rfc/rfc5681.html)
section 3.2. This is an educational cumulative-ACK transport without TCP
handshakes, timestamp options, SACK, delayed ACKs, or receiver-window negotiation.

## Days and event boundaries

Inspected current CPU-shared transition code:

- `executor/src/scalar.rs:3365` (`host_tcp_ack_arrival`): cumulative progress,
  flight-byte removal, partial recovery, one third-duplicate retransmission, and
  further duplicate credit.
- `executor/src/scalar.rs:3563` (`host_retransmission_timeout`): oldest frontier,
  one owned timer, and connection backoff capped at 60 seconds.
- `executor/src/scalar.rs:5871` (`prepare_tcp_attempts`): MSS, remaining total
  bytes, allowance-limited segmentation, and one timer when flight is nonempty.
- `executor/src/tcp.rs:339` and `:545`: recovery frontier and estimator bounds.

This task records source inspection and independent tests, not a new actual
CPU execution. Phase 5's Reno/CUBIC reference work must extend the existing CPU
fixture mechanism. Days clips a future ACK to `next_sequence`; Python rejects
it before state mutation. Days computes its RTT from an echoed attempt time,
while Python deliberately applies the documented conservative Karn policy.
Those are behavior differences, not numerical tolerances.

At an exact ACK/timeout tie, ordinary SimPy events retain insertion ordering.
An ACK scheduled first cancels the timeout; a timeout scheduled first emits one
retransmission before the ACK completes the flow. Both tests run beyond the
next possible timeout and establish no post-completion activity. Days's
arrival-before-timeout phases pick the first behavior deterministically.
Changing the generic timer or replacing SimPy's engine is outside this local
transport repair; the timing documentation must retain this explicit boundary.

## Red/green validation

Before production changes, the first new suite produced **23 failed**. Each
failure reached its intended condition with a finite finish time, rather than
being masked by the old `None`-finish exception. They exposed fractional byte
emission, ignored custom MSS, burst overshoot, start/finish mistakes, ACK
validation, repeated fast retransmit, missing partial recovery, per-segment
timeouts, missing global backoff, synchronous ACK failure, RTT initialization,
and completion feedback. The later 60-second backoff test failed before its
repair; the Boolean ACK test also failed against the initial repair before
explicit Boolean exclusion.

The final new suite run against the accepted baseline module, without changing
working-tree files, produced **31 failed, 2 passed**. The two passing cases are
the explicit SimPy insertion-order tie conventions. This red comparison can be
replayed with:

```sh
uv run --locked python - <<'PY'
import subprocess
import sys
import types
import pytest

baseline = subprocess.check_output(
    ['git', 'show', '9659756:ns/packet/tcp_generator.py'], text=True
)
module = types.ModuleType('ns.packet.tcp_generator')
sys.modules[module.__name__] = module
exec(compile(baseline, '9659756/ns/packet/tcp_generator.py', 'exec'), module.__dict__)
raise SystemExit(pytest.main(['-q', '--tb=no', 'tests/packet/test_tcp_transport.py']))
PY
```

Existing fresh-attempt and Karn tests now obtain their outstanding state from
real sends and actual timers. Their safety intent is preserved. Two incorrect
assertions were corrected: partially acknowledged data retains its unacknowledged
suffix rather than a timer for its ACKed original start; nonexistent outstanding
data cannot produce a controller loss notification. The previous "ignore unknown
frontier" test had required such a notification despite its name. Tests still
assert original packets remain unmodified and outstanding suffix bytes survive.

| Exact command | Observation |
| --- | --- |
| `uv run --locked pytest -q tests/packet/test_tcp_generator.py tests/packet/test_tcp_transport.py tests/flow/test_tcp_integration.py tests/flow/test_tcp_congestion.py --tb=short` | **46 passed**, including 33 new transport cases. |
| `MPLBACKEND=Agg uv run --locked python examples/tcp.py` | Exit 0 with checked-in parameters and observation cutoff 100 s; already emitted loss recovery can continue beyond this cutoff. |
| `git diff --check` | Passed. |

Validation is bounded to this sender and existing related controller/integration
cases. The coordinator owns receiver/BBR integration and the whole-phase gate.

## Source size

Phase 0 AST/token categories, compared against `9659756`. Explanatory lines are
nonblank docstrings/comment-only lines; code-bearing lines are remaining
nonblank lines, including delimiters. Inline comments overlap code-bearing.
The implementation replaces obsolete per-segment timers and lazy reconstruction
rather than adding a general transport framework.

| File/category | Before | After | Change |
| --- | ---: | ---: | ---: |
| `tcp_generator.py` physical | 359 | 332 | -27 |
| Code-bearing | 246 | 244 | -2 |
| Explanatory | 60 | 55 | -5 |
| Blank | 53 | 33 | -20 |
| Inline comments | 3 | 3 | 0 |
| `cc.py` physical | 173 | 182 | +9 |
| Code-bearing | 88 | 90 | +2 |
| Explanatory | 47 | 52 | +5 |
| Blank | 38 | 40 | +2 |
| Inline comments | 1 | 1 | 0 |

Combined production code-bearing and explanatory counts are unchanged; physical
lines decrease by 18. The only shared-controller edit is the documented optional
partial-ACK notification. Tests and evidence are reported separately from
production growth.
