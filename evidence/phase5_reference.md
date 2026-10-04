# Phase 5 actual Days CPU TCP reference

The read-only Days checkout is pinned at
`9ff20eac16dcdf752510b05cbcf526684dc05146` in
`/Users/bli/Playground/days`. `tests/reference/days_tcp.rs` calls
`run_cpu_with_observations` with two workers and `ObservationMode::Full`.
The JSON comes from `cpu.result`, including its Full diagnostic TCP transition
plane. Complete result equality with `run_scalar_with_observations` is asserted
only as a secondary cross-check. No controller output is fabricated by direct
Rust controller calls. Every loss/recovery/timeout transition arises while the
CPU executes the supplied network and transport state.

The helper's direct-host image construction follows the pinned
`executor/tests/tcp_semantics.rs::tcp_image`: public source TCP generator state,
receiver state, first data descriptor, emission event, forward/reverse routes,
and packet channels. It changes the link rate and propagation explicitly and
configures the public initial controller window/threshold where noted below.
The existing regeneration wrapper adds only `--case tcp`; revision/clean-tree
checks, temporary Cargo project, locked dependencies, cleanup, source/lock hashes,
compiler version, and replay-command recording are reused. Normal pytest reads
JSON and needs neither Rust nor Days. No production module is modified here.

## Explicit cases and alignment

All cases use MSS 512 bytes, ACK size 40 bytes, immediate cumulative ACKs,
sequence zero origin, seed 1, and a four-second inclusive CPU horizon. Forward
and reverse propagation are 100 ns per link. The reverse host link is always
8,000,000,000 bit/s. Initial RTO/minimum/maximum are 1/1/60 seconds with 1 ms RTO
clock granularity, matching Python's transport assumptions. No random draws,
ECN, delayed ACK, or SACK are involved.

| Case | Application bytes | Initial cwnd / threshold bytes | Topology | CPU data ACKs / drops / timeouts | Last CPU feedback ns |
| --- | --- | --- | --- | --- | --- |
| Reno growth and short tail | 6267 | 1024 / 65535 | Direct 8 Gbit/s | 13 / 0 / 0 | 6507 |
| Reno avoidance | 6267 | 1024 / 2048 | Direct 8 Gbit/s | 13 / 0 / 0 | 6507 |
| CUBIC growth and short tail | 6267 | 512 / 65535 | Direct 8 Gbit/s | 13 / 0 / 0 | 6747 |
| CUBIC avoidance | 6267 | 512 / 2048 | Direct 8 Gbit/s | 13 / 0 / 0 | 6747 |
| Reno bottleneck loss | 10363 | 4096 / 65535 | 64 Gbit/s source, 8 Gbit/s bottleneck, four waiting slots | 21 / 8 / 0 | 12935 |
| Reno bottleneck timeout | 3195 | 1024 / 65535 | Same links, one waiting slot | 7 / 2 / 2 | 2000003772 |
| CUBIC bottleneck loss | 10363 | 4096 / 65535 | Same links, four waiting slots | 22 / 8 / 0 | 13068 |

Days queue capacity counts waiting packets; its service slot is separate.
The bottleneck topology is source host 0 → switch 2 → receiver host 1, with
reverse ACKs directly from 1 to 0. The direct topology uses hosts 0 → 1 and
1 → 0; it has no switch or admission limit. The generator carries the explicitly
configured state from the start; low thresholds are actual initial input,
not inferred from traces. CUBIC's 65535-byte initial threshold is represented
in Days nanosegments, retaining the fixture's exact scaled value.

All seven cases finish with highest ACK equal to application bytes, zero bytes
in flight, no pending CPU events, and no resident packets. The two large loss
cases include three duplicate ACKs triggering fast retransmit, further
recovery inflation, real cumulative partial recovery ACKs, and a full recovery
exit. The small timeout case actually drops two packets and fires two TCP
retransmission timers. Packet headers retain every data sequence, size, send
attempt time and retransmission flag, plus each ACK frontier and echoed time.

Python end-to-end tests cover **all four direct cases** with ordinary
`TCPPacketGenerator`, `TCPReno`/`TCPCubic`, source/reverse `Port`, `Wire`, and
`TCPSink`. They align Days Reno's two-MSS starting window explicitly rather than
changing Python's one-MSS default. Exact data sequence and size identities,
all link-local departure and receiver/feedback times, cumulative ACK identities
and counts, delivered byte total, 123-byte final segment, sender flight/segment
retirement, and stopped active timers are checked. CPU payload IDs identify
physical attempts; Python packet IDs identify byte sequences. The test maps
CPU IDs through their recorded packet headers to compare the common transport
identity rather than pretending those different ID namespaces are equal.

At 8 Gbit/s, serialization is `8 * bytes / bits_per_second`, exactly one
nanosecond per byte; all four compared direct cases have integral intervals.
Their absolute timing tolerance is 0.000001 ns (one femtosecond), which rejects
one nanosecond. Bottleneck full-MSS source intervals are exactly 64 ns at
64 Gbit/s; a 123-byte short tail takes 15.375 ns and rounds to 16 ns in Days.
Those loss cases supply controller feedback comparisons, not end-to-end timing
equality. Thus their rounding cannot silently widen the direct-case tolerance.

Days includes its horizon; SimPy numeric `run(until=4)` is exclusive. All actual
feedback in the compared finite cases completes strictly before that horizon;
there are no events at the cutoff to lose. Python stopped Timer processes may
retain old inert wakeups until their deadlines, so no equality of event-queue
internals or final `env.now` is asserted. No active retransmission state remains.

## Controller comparison and numerical bounds

Each recorded controller transition retains time, node, flow, input kind,
newly ACKed bytes, pre-feedback flight, cumulative ACK/frontier, fresh RTT,
and exact before/after state. Python replays this explicit feedback through
public controller hooks. Duplicate count, third-duplicate entry, partial/full
recovery decisions, recovery frontier, and phase must match exactly before and
after each event. Reno additionally requires exact byte window, threshold, and
ABC credit. Final newly ACKed bytes sum exactly to the final CPU frontier.

CUBIC compares real Python segment windows against scaled Days state rather
than allowing an arbitrary integer-byte tolerance. Days uses 10^9 nanosegments
per segment and floors integer arithmetic; Python retains floating-point values.
For the no-loss avoidance case the curve origin is four segments, K=0, and
elapsed+RTT remains below 10 microseconds. The cubic target's time sensitivity
is negligible on that interval; each fixed-point target/ACK division loses less
than one nanosegment. The ACK map `w + (target-w)/w` contracts window error for
these positive windows. Ten avoidance ACKs therefore accumulate less than
20 nanosegments of lattice error. The comparator uses 20 nanosegments as a
floating/lattice allowance.

Days also floors each RTT EWMA: `s' = floor((7*s + sample)/8)`.
Starting from the same samples, its difference from the real recurrence obeys
`error' < 7*error/8 + 1 ns`, so it stays below 8 ns. The friendly estimate is
`beta*Wmax + alpha*elapsed/srtt`, where alpha is `3*(1-beta)/(1+beta)`.
Its rounding error is bounded by `alpha*elapsed*8/min_srtt^2` segments.
This branch directly replaces the window, so the bound does not multiply by
ACK count. Each no-loss avoidance comparison uses that timestamp-specific
bound plus 20 nanosegments and asserts the bound is below 0.01 segment
(5.12 bytes). The largest allowed bound in this recorded case is **4.068241
bytes**, and the largest observed real/scaled window difference is **0.903225
bytes**. Thresholds and loss maxima compare within 10 nanosegments; K differs
by at most its one-nanosecond floor plus 0.1 ns floating allowance. Recovery
windows have only float/lattice error because these fixtures have no advancing
congestion-avoidance ACK after the loss recovery exit. This bound is scoped to
these short fixtures; it does not claim a uniform error for arbitrary long
CUBIC trajectories or saturation limits.

## Preserved counterexample and sensitivity

Days supplies an echoed attempt RTT for advancing recovery ACKs. Python
conservatively supplies no fresh RTT during recovery under its Karn policy.
The loss controller replay intentionally feeds **recorded CPU samples** to
CUBIC's ACK method before its partial/exit hooks so the equations can be compared
under the same explicit feedback. It is not a transport-equivalence claim or a
production adapter. A separate test repeats the same genuine CPU feedback
while omitting those recovery RTT samples, as Python transport does, and
requires the comparison to fail.

In the CUBIC loss case, the first partial recovery ACK at 6036 ns (frontier 3072)
has a 1536 ns echoed RTT and moves Days SRTT from 1480 to 1487 ns. Python's
conservative path retains 1480.875 ns. The next partial ACK at 6952 ns
(frontier 3584) has a 916 ns sample and moves Days SRTT to 1415 ns; the retained
Python value differs by 65.875 ns, which exceeds the proven 8 ns quantization
bound. The test rejects this discrepancy. Later post-loss CUBIC trajectories
therefore have no general end-to-end equivalence guarantee; widening RTT or
window tolerances to hide it would be incorrect. Saturation and event ties
remain independently tested/documented elsewhere, not established by these
small CPU fixtures.

Sensitivity tests perturb independent in-memory fixture copies. Increasing
one Reno or CUBIC transition window by one MSS raises `AssertionError`.
Changing the first actual CPU data sequence by one MSS makes the end-to-end
identity comparison fail. Increasing the first CPU departure by one nanosecond
makes the end-to-end timing comparison fail. Unmodified observations pass;
checked-in records never change during these tests.

## Executed validation and size

From `/Users/bli/Playground/ns.py`:

```sh
uv run --locked python tests/reference/regenerate_days_fifo.py \
  --case tcp --days-root /Users/bli/Playground/days
uv run --locked pytest -q tests/flow/test_days_tcp_reference.py \
  tests/port/test_days_fifo.py tests/scheduler/test_days_schedulers.py
rustfmt --edition 2021 --check tests/reference/days_tcp.rs
git -C /Users/bli/Playground/days status --short
```

Actual CPU replay produced seven cases and passed complete secondary Scalar
equality. The combined reference suites passed **31 tests**; the TCP suite
passed **18 tests** including meaningful transition/identity/timing sensitivity
and the recovery RTT counterexample. Formatting passed and the Days tracked
source remained clean. A second locked TCP regeneration to a temporary output
matched the checked-in JSON exactly, including provenance; its temporary output
and Cargo build were removed.

Production growth is zero executable and zero explanatory lines. The retained
Rust helper is 357 lines, Python consumer 284 lines, lock 120 lines, and JSON
observations 8832 lines. The helper is one explicit two-host image builder,
a small bottleneck extension, and JSON emission; it is not a new simulator
execution engine or comparison framework. The wrapper changes one argument
choice line. This reference evidence complements the separate Reno, CUBIC,
and BBR implementation evidence and does not constitute Phase 5 approval.


## Review correction: timeout input provenance

Review of candidate `80294c7` found that the actual timeout CPU image had one
waiting slot, while its emitted input metadata claimed four. The recorded
observations were genuine, but that input declaration was incorrect. A focused
regression first failed with `assert 4 == 1` on the retained fixture.

The helper now reads waiting capacity directly from the configured
`SimulationImage` switch queue and source rate from the configured link before
emitting input metadata. It no longer repeats either configuration condition.
Actual two-worker Full CPU regeneration corrected timeout capacity to one and
updated the helper source hash; all seven observation outputs stayed identical.
The focused regression requires the one-slot declaration and the scenario's
two actual drops and two actual timeout transitions. The complete TCP/reference
suites passed 18/31 tests. Rust formatting and whitespace checks passed, and
Days stayed clean. A second locked regeneration exactly matched the corrected
fixture, including its provenance.
