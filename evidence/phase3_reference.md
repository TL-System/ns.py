# Phase 3 current Days CPU scheduler comparison

Reference: clean Days checkout at
`9ff20eac16dcdf752510b05cbcf526684dc05146`, read-only at
`/Users/bli/Playground/days`. `tests/reference/days_schedulers.rs` executes the
public CPU observation API with two workers and full observations. Its complete
CPU result equals the Scalar result for all five cases; Scalar is only a
secondary cross-check. The JSON departures and arrivals come from `cpu.result`.

The recorded fixture is `tests/reference/days_schedulers.json`. Its retained
Rust helper and dependency lock are next to it. The existing FIFO replay wrapper
accepts `--case schedulers`; omitting that option keeps the original FIFO replay.
This small extension avoids another copy of the revision/clean-tree checks,
temporary Cargo build, and provenance recording. The FIFO Rust source, lock,
and JSON have not changed. Compilation and Cargo output stay in temporary
directories outside both source trees. Ordinary pytest consumes JSON without
Rust or a Days checkout. No production source changes belong to this task.

## Explicit inputs and observations

All cases preload explicit arrivals to switch node 1, after their source hop,
with route links `[0, 1]`. There is one unbounded switch egress at
8,000,000,000 bit/s followed by 100 ns propagation, seed 18, and no loss or random
input. Class IDs equal flow IDs; the helper supplies one flow for each class.
Days' modulo classifier therefore has the same result as Python's identity
classifier for these inputs. SP priorities are `[1, 9, 9]`; larger values win.
DRR uses the exact byte quanta recorded in the fixture, matching Python's
configured fixed quanta, rather than matching weight labels alone.

At this rate, `8 * bytes / bits_per_second` is one nanosecond per byte. Every
serialization interval is integral, so there is no Days rounding discrepancy.
The absolute comparator tolerance of 0.000001 ns is one femtosecond, for
floating-point accumulation only. Identities must agree exactly before timing
is compared. A one-nanosecond change fails.

Each input tuple below is `(packet ID, class ID, bytes, arrival ns)`. Each output
tuple is `(packet ID, departure ns)`. Full admission and delivery observations,
counters, compiler version, command, source hash, and lock hash are in the JSON.
Deliveries occur exactly 100 ns after the listed departures.

| Case | Explicit input | Actual CPU departures |
| --- | --- | --- |
| SP boundaries, ties, idle | `(0,0,1000,0)`, `(3,1,250,0)`, `(6,0,500,100)`, `(9,2,125,250)`, `(12,1,125,250)`, `(15,1,125,750)`, `(18,0,125,5000)` | `(3,250)`, `(9,375)`, `(12,500)`, `(0,1500)`, `(15,1625)`, `(6,2125)`, `(18,5125)` |
| DRR credit carry, idle | `(0,0,4000,0)`, `(3,1,1000,0)`, `(6,1,2500,0)`, `(9,0,1000,0)`, `(12,1,500,0)`, `(15,0,2000,15000)`; quanta `[1500,3000]` bytes | `(3,1000)`, `(6,3500)`, `(12,4000)`, `(0,8000)`, `(9,9000)`, `(15,17000)` |
| DRR activation order difference | `(0,1,1000,0)`, `(3,0,1000,0)`; quanta `[1500,1500]` bytes | `(3,1000)`, `(0,2000)` |
| WFQ initial tags, ties, idle | `(0,0,1000,0)`, `(3,1,500,0)`, `(6,1,1500,0)`, `(9,0,1000,5000)`; weights `[1,2]` | `(3,500)`, `(0,1500)`, `(6,3000)`, `(9,6000)` |
| WFQ active clock difference | `(0,0,10,0)`, `(3,1,100,0)`, `(6,2,13,0)`, `(9,3,14,0)`, `(12,4,10,15)`; five unit weights | `(0,10)`, `(6,23)`, `(9,37)`, `(12,47)`, `(3,147)` |

SP's later high-priority initial arrival is visible before service starts. Two
equal-priority classes arriving at the 250 ns completion keep their arrival
order. Packet 15 arrives during packet 0's service and cannot preempt it. The
last packet begins a new busy period. The independent expected order and both
departure and delivery times match Python.

For DRR's shared case, class 0's 4000-byte head needs three 1500-byte visits;
class 1 first sends 1000 bytes and retains 2000 bytes, then receives another
3000 bytes before sending 2500 and 500 bytes. Class 0 then sends 4000 bytes,
retains 500 bytes, and needs another visit for its 1000-byte next packet. The
2000-byte packet after the idle interval also exceeds one quantum. These
selection decisions and times match Python's independent fixed-quantum tests.
This fixture does not assert equality of all internal DRR deficit state.

The second DRR case intentionally differs. Class 1 activates first and class 0
activates second at the same timestamp. Python's textbook active FIFO serves
packet 0 then packet 3, at 1000 and 2000 ns. Days starts a numeric class rotation
at class 0 and serves packet 3 then packet 0. The test requires both respective
orders and records their inequality. Equal weights and quanta do not establish
general DRR equivalence. Deficit reset and arrival-during-service behavior need
the independent DRR algorithm tests as well.

## WFQ recurrence boundary

The initial-tag fixture has normalized byte-work finish tags 1000 for packet 0,
250 for packet 3, and 1000 for packet 6. Packet 3 goes first; packets 0 and 6 have
equal tags and retain canonical arrival order. There are no arrivals during that
busy period, and the last packet arrives after both physical and fluid backlog
have drained. This case can compare the two recurrences' shared decisions.

The active-clock fixture identifies a substantive difference. Days removes a
class's weight when its last physical packet completes. Its normalized virtual
work at 10 ns is `10/4 = 5/2`; at 15 ns it is `5/2 + 5/3 = 25/6`. The new
class-4 packet gets finish tag `25/6 + 10 = 85/6`, greater than class 3's tag 14.
After packet 6 completes at 23 ns, Days therefore selects packet 9.

In textbook GPS, no initial class has exhausted its fluid work by 15 ns. The
clock is `15/4`; the new packet's tag is `15/4 + 10 = 55/4`, between class 2's
tag 13 and class 3's tag 14. GPS-based packet selection would choose packet 12
at 23 ns, producing `(0,10)`, `(6,23)`, `(12,33)`, `(9,47)`, `(3,147)`.
This is a decision change, not a numerical tolerance issue. The fixture preserves
the actual CPU result. Python WFQ expectations remain pending the user's
explicit recurrence choice; this task has not selected or changed production
WFQ semantics.

## Executed validation

From `/Users/bli/Playground/ns.py`:

```sh
uv run --locked python tests/reference/regenerate_days_fifo.py \
  --case schedulers --days-root /Users/bli/Playground/days
uv run --locked pytest -q tests/scheduler/test_days_schedulers.py \
  tests/port/test_days_fifo.py
rustfmt --edition 2021 --check tests/reference/days_schedulers.rs
git -C /Users/bli/Playground/days status --short
```

The scheduler replay produced all five cases with matching CPU/Scalar results.
The targeted Python suites passed: **11 passed**. Rust formatting passed; the
Days status output was empty. Each case conserves all supplied packet identities
and byte counts, has no drops, and leaves no events or resident packets. Python
also checks object identity, final waiting counters, the in-service packet,
PacketSink packet/byte accounting, and exact input admissions.

The old default FIFO command was executed with `--output` pointing inside a
`tempfile.TemporaryDirectory`. Parsing the output and comparing it with the
unchanged checked-in FIFO JSON gave exact dictionary equality, including all
reference metadata. The temporary replay file and Cargo output were removed.

An in-memory comparator sensitivity check loaded `test_days_schedulers.py`,
copied the SP departure records, swapped its first two departures, and called
`test_shared_scheduler_decisions_and_times_match_days_cpu`. It raised
`AssertionError`. Repeating with only the first departure increased by 1 ns also
raised `AssertionError`. Restoring the in-memory records passed. The checked-in
fixture was never mutated. These checks establish harness sensitivity, not a
pre-existing production bug.

Production line growth is **zero code-bearing and zero explanatory lines**.
Replay and comparison logic remain test-side; no Rust dependency is introduced
into normal simulation or pytest execution. This evidence covers reference
replay only; Phase 3 acceptance also requires the scheduler implementation,
composition reviews, and integrated validation.
