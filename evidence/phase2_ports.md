# Phase 2 packet movement and accounting

Implemented against accepted Phase 1 `807c35d` on 2026-10-03. The comparison
checkout remains Days `9ff20eac16dcdf752510b05cbcf526684dc05146`. This task owns
`packet/packet.py`, `packet/sink.py`, `port/port.py`, `port/wire.py`, and the small
associated correction to `port/monitor.py`. The orchestration snapshot identifies
the review candidate; this implementer made no commits or pushes.

## Audit and behavior

`Packet` carries bytes and simulation seconds, preserving object identity through
FIFO and wire movement. Each packet owns separate priority and per-hop mappings.
Its original generation timestamp is not changed by these elements. Link elements
treat the optional payload as opaque; size alone determines serialization.
Days's packet/image records use integer byte counts and nanoseconds instead.
Fractional packet sizes remain supported here for queueing examples.

`Port` accepts an exact capacity fit, including `qlimit=1`, and drops only when
the resulting occupancy exceeds capacity. Its documented capacity includes local
service and packets retained for downstream backpressure. `byte_size` consistently
counts all resident bytes. Ordinary completion releases them at every rate,
including unlimited rate zero. A zero-buffer downstream handoff retains them until
the downstream removes its store reference and calls `update(packet)` exactly
once. A delayed release while the next local packet is in service changes only
the released packet's accounting. The local process waits on a store and, for
positive rates, on `8 * packet_bytes / rate_bps` seconds. Rate zero adds no
serialization timeout and still yields a store event on every loop.

Packet admission uses received minus dropped minus released, rather than the
physical store length. SimPy can synchronously remove an arrival to satisfy an
idle `Store.get()` before the process resumes and marks the packet busy. That
handoff must not let an immediate second arrival bypass capacity. Normal departure
also clears local busy state and releases occupancy before calling downstream
`put()`, which can synchronously inject new traffic.

`PortMonitor` uses that same conservation count and resident bytes. Queue-only
samples subtract the port's local service once; samples including service retain
the total. Zero-buffer packets remain queued/retained until their callback,
including when a downstream element serves them. This avoids adding a second
copy of a locally served packet still represented in the upstream store. The
inherited accounting fields also work with `REDPort`; its averaging/signaling
algorithm remains a Phase 6 audit.

`Wire` retains its own entry timestamp with each queued packet. A second wire
receiving the same object can change diagnostic `Packet.current_time` without
changing the first wire's propagation deadline. Constant propagation overlaps
between packets: a 1-second FIFO serialization followed by a 2-second wire yields
deliveries at 3, 4, and 5 seconds for three packets. Variable delays retain the
existing FIFO convention: arrival is no earlier than the previous delivery or
this entry plus its sampled delay. Loss draws and delay samples keep their
existing evaluation order. The `put()`/`out` API and `current_time` diagnostic
metadata are preserved; the internal wire store now carries `(packet, entry_time)`
records rather than bare packets.

`PacketSink` keeps packet/byte counters and first/last arrival times independently
of sample-recording flags. Arrival grouping follows `flow_id` or `src` as selected.
Inter-arrival samples remain per group, with the first interval beginning at zero.
Waits are end-to-end elapsed seconds from `Packet.time`, not a queue-only delay.
Recorded per-hop dictionaries are snapshots so later packet mutations cannot
rewrite prior observations. Ten simultaneous arrivals no longer make optional
debug throughput output divide by zero. Days supplies arrival observations but
has no matching statistics collector; these telemetry invariants are independent
tests.

## Days CPU boundaries

Inspection used `executor/src/cpu.rs`'s shared transition path and the following
current implementation points in `executor/src/scalar.rs`: switch arrival's
`drop_mark_decision`, `switch_queue_bytes` increments on admission and decrements
on selection, and link arrival/departure emission. `executor/src/time.rs` computes
`ceil(8 * bytes * 10^9 / rate_bps)` per serialization. These agree on FIFO,
non-preemptive serialization, and propagation added after serialization. Python
keeps floating-point seconds without per-step nanosecond ceiling, and its rate
zero convention has no Days link counterpart.

Days tail-drop capacity measures waiting packets, excluding in-service packets,
and Days capacity zero means unlimited. Python preserves its public service-inclusive
capacity and uses `None` for unlimited. A busy queue may align a Days waiting limit
K to Python total limit K+1, but that arithmetic is not a universal mapping for
an initially idle simultaneous burst. The actual small CPU fixture therefore uses
unlimited capacity on both sides; local bounded-capacity tests establish this
component's separate contract. Its fixture, regeneration command, and observations
are maintained by the reference task under [tests/reference](../tests/reference/README.md).

Days's fixed-delay links have no variable-delay FIFO-wire counterpart. Equal-time
arrival/selection order remains SimPy's event insertion order, whereas Days orders
phases. Numeric `env.run(until=t)` excludes an ordinary delivery at exactly t;
Days processes its inclusive stop. A separate wire test verifies this boundary,
then drains remaining work. The finite hand calculations use `env.run()` to drain
all ordinary events. No event engine or cross-engine ordering policy was added.

## Red/green validation

The tests were written first. The original targeted command failed with **13
failed, 8 passed**, demonstrating exact-fit/one-packet rejection, unlimited byte
leakage, service/retained monitoring errors, wire timestamp corruption (15 seconds
instead of 12), missing first/last telemetry when recording is disabled, mutable
per-hop observation aliasing, and debug division by zero. Four later invariant
cases cover delayed retained release during next service, monitor release samples,
and zero capacity in bytes/packets.

| Exact command | Final observation |
| --- | --- |
| `uv run --locked pytest -q tests/port/test_port.py tests/port/test_wire.py tests/packet/test_packet.py tests/packet/test_sink.py` | 25 passed in 0.03 s. |
| `uv run --locked pytest -q` | 105 passed in 0.13 s, including the other Phase 2 tasks' current tests. |
| `uv run --locked python examples/two_level_sp.py` | Exit 0; six flows each delivered three packets. |
| `uv run --locked python examples/two_level_drr.py` | Exit 0; six flows each delivered three packets. |
| `uv run --locked python examples/two_level_wfq.py` | Exit 0; six flows each delivered three packets. |
| `git diff --check` | Passed. |

The two-level examples use their checked-in finite inputs and stop at 100 seconds.
They provide compatibility smoke coverage for callback forwarding, not acceptance
of the scheduler algorithms, whose independent audits remain Phase 3.

## Source growth

Counts use Phase 0's AST/token categories and compare these five production files
with `807c35d`. Explanatory lines are docstrings and comment-only lines; code-bearing
lines include delimiters and inline comments, not just executable statements.

| Category | Before | After | Change |
| --- | ---: | ---: | ---: |
| Physical | 450 | 478 | +28 |
| Code-bearing | 245 | 245 | 0 |
| Explanatory | 137 | 166 | +29 |
| Blank | 68 | 67 | -1 |
| Inline comments (overlap code-bearing) | 7 | 5 | -2 |

The changes use the existing stores, process loops, and `put()` composition.
One cumulative release counter closes packet conservation without introducing
a packet registry or another execution layer.
