# Correctness modernization

ns.py is an educational simulator: keep its small, readable SimPy processes and
`put()`/`out` composition while correcting the network algorithms. Prefer a local
repair to a new abstraction. Preserve existing imports, constructor conventions,
and zero-buffer composition where practical; explain necessary behavior changes.
Do not add an execution engine, configuration framework, or Days-only protocols.

Comments are part of the design. Explain state, units, algorithmic intent, timing,
and boundary cases liberally and accurately. Give each changed SimPy process a
docstring describing its waits. Keep textbook concepts recognizable and cite
algorithm references where they resolve a subtle choice. Report executable and
explanatory line growth separately; neither terse code nor stale comments improve
readability. A networking student should be able to follow the implementation.

## Baseline and reference

- ns.py: `0e9011523a668a8d3d79139cf42cff65643dffa4`.
- Days: `9ff20eac16dcdf752510b05cbcf526684dc05146`, initially at
  `~/Playground/days`.
- Baseline measurements and commands: [Phase 0 evidence](../evidence/phase0.md).
- Transport assumptions already established: [TCP timing](tcp_timing.md).

Current Days CPU execution is the comparison target. Its `executor/src/cpu.rs`
uses the transition logic in `executor/src/scalar.rs`; Scalar is useful for
understanding a discrepancy, but a Scalar-only result does not establish a CPU
comparison. The [legacy Days paper](https://days.sh/papers/days.pdf) provides
historical design context. Legacy code is a secondary algorithm reference, not
evidence that a feature exists in the current CPU backend.

## Comparison contract

Use explicit packet sizes, arrival times, routes, classes, traffic volumes, and
loss schedules. Align link rates, propagation delays, queue capacities, initial
windows, MSS, ACK sizes, and timer parameters. Equal random seeds across different
engines do not establish equal inputs. Record reference revision, command,
configuration, and observations with each checked-in fixture.

Compare packet selection, delivery/drop identity, cumulative ACKs, retransmission
decisions, and controller transitions before aggregate throughput. Follow the
first divergent decision. Numeric tolerance cannot excuse a changed scheduler,
lost byte, or spurious timeout. Do not require unrelated same-time events on
different links to appear in the same global trace order.

| Concern | Contract and known difference |
| --- | --- |
| Units | ns.py uses seconds, bytes for packet sizes and TCP sequences/windows, and bits/second for link rates. Serialization is `8 * bytes / rate_bps`; document any controller-specific rate convention. Days uses integer nanoseconds and byte counts. |
| Rounding | Days `executor/src/time.rs` rounds each serialization interval up to a nanosecond. ns.py retains floating-point intervals. Prefer integral-nanosecond fixtures first. For fractional cases, derive a bound from the number of causal serialization steps (less than one nanosecond rounding per step) plus floating-point error; document controller quantization separately. Never widen a tolerance to hide a decision change. |
| Equal-time events | Days keys order by time, phase, origin node, and origin sequence: arrivals phase 0, completion/timeouts/pacing phase 1, selection phase 2. SimPy orders by time, priority, then event insertion. Exercise same-link selection and ACK/timeout boundaries explicitly. Correct local behavior where needed; document irreducible boundary differences without replacing SimPy. |
| Stop time | Days processes its inclusive stop time. Numeric `env.run(until=t)` stops before ordinary events at `t`. Use an explicit test-side observation cutoff/drain convention and compare the same interval; test the boundary separately. |
| Occupancy | Distinguish waiting packets, the packet in service, and packets retained for downstream backpressure. Document admission and measurement semantics independently; align reference capacity before comparing a drop. |
| Random behavior | Inject reproducible observations/draws where appropriate. Current Days RED uses deterministic counter signaling; ns.py uses random draws. Compare shared averaging, threshold, and capacity rules, and test each signaling model independently. |
| Missing counterparts | Use independent algorithm/specification tests and record the gap. Current CPU has no BBR or Virtual Clock scheduler. Do not present legacy output as current CPU equivalence. |

Before Phase 2 passes, execute a small FIFO scenario with actual Days CPU output
and compare it with ns.py. Keep the regeneration tool and fixtures under tests,
for example `tests/reference/`; use the public CPU observation API and departure
records. Extend this small mechanism for schedulers and Reno/CUBIC. Ordinary
Python tests consume recorded fixtures without Rust or a Days checkout. Avoid a
general cross-simulator framework.

## Phases and acceptance

Complete each phase's implementation, reviews, validation, and publication before
starting the next. Tasks inside a phase may run independently when files and
dependencies permit. Every behavioral fix needs a failing reproducer followed by
a passing invariant/observable-behavior test, not assertions that copy the code.

| Phase | Work | Acceptance |
| --- | --- | --- |
| 0. Baseline | Record revisions, tests, examples, source counts, and component map below. Identify reference gaps and comparison rules. | Every source module has an audit destination; baseline failures are explicit. |
| 1. Python and packages | Target Python 3.14; resolve current stable compatible dependencies, lockfile, packaging, CI, and instructions. Declare test dependencies. Replace indiscriminate example execution with finite headless smoke tests. | Clean sync, pytest, curated examples, distribution build and install pass. No simulator behavior changes mixed in. |
| 2. Movement and accounting | Packet, FIFO port, wire, timer, tagged store, delay utilities, and basic sink. Audit units, admission boundaries, ownership, cancellation/restart, and zero-buffer forwarding. | Hand-calculated timing, conservation, capacity, exactly-once accounting, idle/unlimited-rate cases pass; actual CPU FIFO comparison is reproducible. |
| 3. Schedulers | Separate SP, DRR, WFQ, and Virtual Clock tasks, then composed schedulers/switches. Audit service-start selection, non-preemption, class mapping, ties, idle transitions, and telemetry. | Independent expected orders/times and applicable CPU fixtures pass; two-level composition preserves identity and accounting. No unexplained starvation or idle service with eligible traffic. |
| 4. TCP mechanics | Audit both `TCPPacketGenerator` and `BBRPacketGenerator`, plus receiver: segmentation, ACKs, in-flight bytes, retransmission ownership, RTT/RTO, and timer lifetime. Preserve intentional pacing differences. | Short final segments, data/ACK loss, duplicate/reordered data, partial ACKs, and ACK/timeout boundaries pass. Application bytes are delivered exactly once and ACKs cover only contiguous data. Completion leaves no active retransmission behavior; timing documentation agrees. |
| 5. Congestion control | Separate Reno, CUBIC, and BBR tasks. Exercise explicit feedback transitions before full flows. Establish the implemented BBR variant and its documented simplifications; audit delivery-rate sampling and pacing. | Reno/CUBIC agree with the aligned Days model within justified quantization differences. BBR independently passes application-limited, loss, sampling, pacing, and probe-state cases for its documented variant. |
| 6. Remaining components | RED, shapers/marker, traffic sources, demultiplexers/splitters, monitors, flows, topology/routing, config, and proxies. Use small component-family tasks. | Every inventory row is closed with tests or recorded inspection. Rate/burst envelopes, routing, measurement definitions, and bounded socket lifecycle are verified. |
| 7. Composition and simplification | Bottleneck, hierarchical scheduler, and small FatTree scenarios with mixed sizes, congestion, and TCP loss. Remove obsolete state/instrumentation; update educational examples and behavior notes. | Full regression suite, curated examples, reference fixtures, and package build/install pass. Remaining differences are explained; production growth and readability receive a final review. |

DRR review must independently examine fixed quantum, deficit carry/reset, active
order, and packets larger than a quantum; current tests requiring automatic
quantum inflation are not an algorithm specification. WFQ review must examine
virtual time, active weights, finish tags, and idle periods. SP must preserve
within-class FIFO and non-preemption; Virtual Clock must establish tag units and
idle-clock updates against its own algorithm reference.

The user's Phase 3 decision is to match current Days WFQ: classes are active
while they have queued or in-service physical packets, and their weights retire
at local packet completion. This packet-active recurrence approximates fluid
GPS and can choose a different next packet; the counterexample is preserved in
the CPU reference evidence. Python uses second-based floating-point tags; Days
uses rate-scaled exact rational tags. Their common scaling preserves mathematical
ordering, subject to Python floating-point rounding and the documented event
ordering boundary.

## Component inventory

Paths below are relative to `ns/` and the pinned Days checkout respectively.
“Shared” means a comparable behavior, not a one-to-one public component. Every
row below is closed by observable tests and reference evidence, or explicit
package inspection. Recorded acceptance is linked separately from task-local
checks; the Phase 7 final integrated gate is recorded by the coordinator.

| Python module(s) | Days reference or gap | Phase | Closed: tests or inspection evidence |
| --- | --- | --- | --- |
| `packet/packet.py` | Shared `executor/src/model.rs`, `event.rs`, `image.rs` packet/identity records | 2 | [Packet/port evidence](../evidence/phase2_ports.md); `tests/packet/test_packet.py`: size, identity, payload, timestamp ownership. |
| `packet/sink.py` | Shared `executor/src/scalar.rs` arrival observations; no matching statistics collector | 2, 6 | [Phase 2](../evidence/phase2_ports.md), [Phase 6 inspection](../evidence/phase6_routing_utilities.md); `tests/packet/test_sink.py`: physical counts, delay and per-hop snapshots. |
| `port/port.py` | `executor/src/scalar.rs` FIFO/admission/service; `model.rs`, `time.rs` | 2 | [Port evidence](../evidence/phase2_ports.md); `tests/port/test_port.py`, `test_days_fifo.py`: conservation, exact capacity, CPU FIFO timing. |
| `port/wire.py` | Shared link propagation in `executor/src/scalar.rs`, `time.rs`; legacy `flows/wire.rs` for historical API | 2 | [Wire evidence](../evidence/phase2_ports.md); `tests/port/test_wire.py`: entry-relative overlapping delays, FIFO and loss. |
| `utils/timer.py` | Shared TCP timer lifecycle in `executor/src/scalar.rs`; no generic callback timer | 2, 4 | [Utility evidence](../evidence/phase2_utilities.md), [transport acceptance](../evidence/phase4.md); `tests/utils/test_timer.py`: cancel, restart, one-shot lifetime. |
| `utils/taggedstore.py` | No generic SimPy store counterpart; scheduler ordering in `executor/src/scalar.rs` | 2 | [Utility evidence](../evidence/phase2_utilities.md), [composition](../evidence/phase3_composition.md); `tests/utils/test_taggedstore.py`: stable ties, capacity, exact-object get. |
| `utils/delayer.py` | No direct counterpart for `Delayer`/`StackDelayer`; independent timing/ownership tests | 2 | [Utility evidence](../evidence/phase2_utilities.md); `tests/utils/test_delayer.py`: FIFO deadlines, byte-rate serialization, packet ownership. |
| `scheduler/sp.py`, `drr.py`, `wfq.py` | `executor/src/model.rs`, `scalar.rs`; scheduler fixtures in `executor/tests/` | 3 | [Scheduler acceptance](../evidence/phase3.md), [CPU references](../evidence/phase3_reference.md); `tests/scheduler/test_sp.py`, `test_drr.py`, `test_wfq.py`, `test_days_schedulers.py`: independent order/timing and explicit variant counterexamples. |
| `scheduler/virtual_clock.py` | No current CPU counterpart; `legacy/src/schedulers/vc.rs` plus algorithm reference | 3 | [Virtual Clock evidence](../evidence/phase3_virtual_clock.md); `tests/scheduler/test_virtual_clock.py`: tag units, idle clocks, ties and nonpreemption. |
| `switch/switch.py` | Shared switch egress behavior in `executor/src/scalar.rs`; `src/topos/build.rs` | 3, 6 | [Composition](../evidence/phase3_composition.md), [routing inspection](../evidence/phase6_routing_utilities.md); `tests/scheduler/test_composition.py`, `tests/topos/test_routing.py`: all disciplines, capacity and actual forwarding. |
| `packet/tcp_generator.py`, `tcp_sink.py` | `executor/src/scalar.rs` host TCP transitions, `tcp.rs`, `tcp_ledger.rs` | 4 | [Transport acceptance](../evidence/phase4.md), [TCP timing](tcp_timing.md); `tests/packet/test_tcp_transport.py`, `test_tcp_sink.py`, `test_tcp_transport_integration.py`: byte ranges, recovery, timers, unique delivery. |
| `packet/bbr_generator.py` | Shared transport invariants above; no current CPU BBR sender | 4, 5 | [Sender](../evidence/phase4_bbr_sender.md), [BBR](../evidence/phase5_bbr.md); `tests/packet/test_bbr_transport.py`: transport invariants, pacing, loss and synchronous ACKs. |
| `flow/cc.py`, `cubic.py` | `executor/src/tcp.rs` Reno/CUBIC | 5 | [Reno](../evidence/phase5_reno.md), [CUBIC](../evidence/phase5_cubic.md), [actual CPU](../evidence/phase5_reference.md); `tests/flow/test_reno.py`, `test_cubic.py`, `test_days_tcp_reference.py`. |
| `flow/bbr.py`, `packet/rate_sample.py` | No current CPU BBR; historical `legacy/src/flows/bbr.rs` is secondary; independently establish variant | 5 | [BBR evidence](../evidence/phase5_bbr.md), [model](bbr.md); `tests/packet/test_rate_sample.py`, `tests/flow/test_bbrv3.py`, `test_bbrv3_integration.py`: sampling, rounds, probes and recovery. |
| `port/red_port.py` | `executor/src/model.rs` RED state and `scalar.rs` drop/mark decisions; signaling models differ | 6 | [RED evidence](../evidence/phase6_queues_shapers.md); `tests/port/test_red_port.py`: EWMA, thresholds, explicit random draws, capacity and retention. |
| `shaper/token_bucket.py`, `two_rate_token_bucket.py` | No direct current CPU token-bucket shaper; independent rate/burst invariants | 6 | [Shaper evidence](../evidence/phase6_queues_shapers.md); `tests/shaper/test_token_buckets.py`: envelopes, refill, oversized borrowing, colors, peak completion and retained release. |
| `utils/misc.py` | `TrTCM`: no direct current CPU marker; RFC 2698 | 6 | [Marker evidence](../evidence/phase6_queues_shapers.md); `tests/utils/test_trtcm.py`: independent color-blind transitions and byte/bit units. |
| `packet/dist_generator.py`, `trace_generator.py` | Shared generation/preloaded input in `executor/src/scalar.rs`, `image.rs`; `src/utils/testgen/trace.rs`; distributions differ | 6 | [Source evidence](../evidence/phase6_sources.md); `tests/packet/test_dist_generator.py`, `test_trace_generator.py`: exact byte tails, deadlines, trace order and CPU input tape. |
| `utils/generators/MAP_MSP_generator.py`, `pareto_onoff_generator.py` | No direct current CPU counterpart; validate mathematical inputs and generated timing | 6 | [Generator evidence](../evidence/phase6_sources.md); `tests/utils/generators/test_map_msp.py`, `test_pareto_onoff.py`: balance, stationary initialization, batch timing and bit-budget burst endpoint. |
| `flow/flow.py` | Shared flow/application configuration in `executor/src/image.rs`, `src/scenario/compile.rs`; application models differ | 6 | [Flow evidence](../evidence/phase6_sources.md); `tests/flow/test_flow.py`: retained streaming arrivals, inclusive polls, exclusive finish and volume. |
| `demux/fib_demux.py`, `flow_demux.py`, `random_demux.py` | Shared routing in `src/topos/route.rs`, executor route records; no generic/random demux counterpart | 6 | [Routing evidence](../evidence/phase6_routing_utilities.md); `tests/demux/test_demux.py`: terminal/default routes, exact local drops and relative random weights. |
| `utils/splitter.py` | No direct current CPU packet-copy splitter; verify identity and mutable metadata isolation | 6 | [Splitter evidence](../evidence/phase6_routing_utilities.md); `tests/utils/test_splitter.py`: branch identity and mutable metadata isolation. |
| `port/monitor.py`, `scheduler/monitor.py` | Shared observations in `executor/src/scalar.rs`; no matching sampling monitor | 3, 6 | [Monitor evidence](../evidence/phase6_routing_utilities.md); `tests/port/test_port_monitor.py`, `tests/scheduler/test_server_monitor.py`: resident versus waiting/service definitions and positive intervals. |
| `topos/fattree.py`, `utils.py` | `src/topos/build.rs`, `config.rs`, `route.rs`; `src/scenario/compile.rs` | 6 | [Topology evidence](../evidence/phase6_routing_utilities.md); `tests/topos/test_routing.py`: independent node/link counts, shortest paths, reverse ACK routes and GraphML. |
| `utils/config.py` | Shared configuration purpose in `src/topos/config.rs`; Python singleton/YAML semantics independent | 6 | [Config evidence](../evidence/phase6_routing_utilities.md); `tests/utils/test_config.py`: retryable singleton, YAML defaults and key-type preservation. |
| `packet/proxy_generator.py`, `proxy_sink.py` | No current CPU real-socket emulation counterpart; bounded local socket tests | 6 | [Proxy evidence](../evidence/phase6_proxies.md), [limits](proxies.md); `tests/packet/test_proxy_io.py`: bounded local sockets, payload/flow identity, delayed delivery, EOF and explicit cleanup. |
| `utils/retained_store.py` (added in Phase 3) | No generic current CPU ownership store | 3, 7 | [Composition evidence](../evidence/phase3_composition.md); `tests/scheduler/test_composition.py`, `tests/shaper/test_token_buckets.py`: exact identity, preserved FIFO/heap order, pending-put wakeups and callback chain. |
| `__init__.py` | Python package metadata; no algorithm counterpart | 1, 7 | Inspected: only `__version__ = "0.4.5"`; metadata agrees with `pyproject.toml`. [Import/API inspection](../evidence/phase7_readability.md); isolated wheel validation is a final phase gate. |
| `demux/__init__.py` | Python package metadata; no algorithm counterpart | 1, 7 | Inspected: empty package marker; no eager imports or re-exports. [Import/API inspection](../evidence/phase7_readability.md); isolated wheel validation is a final phase gate. |
| `flow/__init__.py` | Python package metadata; no algorithm counterpart | 1, 7 | Inspected: empty package marker; no eager imports or re-exports. [Import/API inspection](../evidence/phase7_readability.md); isolated wheel validation is a final phase gate. |
| `packet/__init__.py` | Python package metadata; no algorithm counterpart | 1, 7 | Inspected: empty package marker; no eager imports or re-exports. [Import/API inspection](../evidence/phase7_readability.md); isolated wheel validation is a final phase gate. |
| `port/__init__.py` | Python package metadata; no algorithm counterpart | 1, 7 | Inspected: empty package marker; no eager imports or re-exports. [Import/API inspection](../evidence/phase7_readability.md); isolated wheel validation is a final phase gate. |
| `scheduler/__init__.py` | Python package metadata; no algorithm counterpart | 1, 7 | Inspected: empty package marker; no eager imports or re-exports. [Import/API inspection](../evidence/phase7_readability.md); isolated wheel validation is a final phase gate. |
| `shaper/__init__.py` | Python package metadata; no algorithm counterpart | 1, 7 | Inspected: empty package marker; no eager imports or re-exports. [Import/API inspection](../evidence/phase7_readability.md); isolated wheel validation is a final phase gate. |
| `switch/__init__.py` | Python package metadata; no algorithm counterpart | 1, 7 | Inspected: empty package marker; no eager imports or re-exports. [Import/API inspection](../evidence/phase7_readability.md); isolated wheel validation is a final phase gate. |
| `topos/__init__.py` | Python package metadata; no algorithm counterpart | 1, 7 | Inspected: empty package marker; no eager imports or re-exports. [Import/API inspection](../evidence/phase7_readability.md); isolated wheel validation is a final phase gate. |
| `utils/__init__.py` | Python package metadata; no algorithm counterpart | 1, 7 | Inspected: empty package marker; no eager imports or re-exports. [Import/API inspection](../evidence/phase7_readability.md); isolated wheel validation is a final phase gate. |
| `utils/generators/__init__.py` | Python package metadata; no algorithm counterpart | 1, 7 | Inspected: empty package marker; no eager imports or re-exports. [Import/API inspection](../evidence/phase7_readability.md); isolated wheel validation is a final phase gate. |

Accepted phase evidence: [0](../evidence/phase0.md), [1](../evidence/phase1.md),
[2](../evidence/phase2.md), [3](../evidence/phase3.md),
[4](../evidence/phase4.md), [5](../evidence/phase5.md),
[6](../evidence/phase6.md). Final model limits and behavior changes are summarized
in [model notes](model_notes.md); [Phase 7 readability](../evidence/phase7_readability.md)
records all production source counts, import inspection, and comment corrections.
[Phase 7 composition](../evidence/phase7_composition.md) records the final teaching
scenario and mixed-size, congestion, hierarchy, and loss integration checks.

## Execution and review

Follow the [requested harness](https://baochun.org/2026-09-05/) with the user's
explicit override to use internal Codex subagents instead of herdr. Use a fresh
implementer and reviewer per task, concrete acceptance criteria, and no nested
delegation. The user's latest override requires every internal subagent,
including implementers, task reviewers, and phase gates, to use gpt-6.1-sol/high.
Reuse the implementer for fixes and a fresh reviewer
for each review cycle. Resolve substantive findings without expanding scope or
weakening tests. Skip mechanical tests for reversible documentation-only edits.

Reviews identify the exact candidate commit. Phase approval precedes the accepted
phase commit. Record acceptance, integrate, validate the merged tree, push, then
clean only task-owned resources. Keep the implementer available until integration
passes. Open a PR after Phase 0 and update it each phase. Preserve essential
evidence in `evidence/`; keep build output out of commits. Genuine scope conflicts
go to the user. Each review includes comment accuracy, documented simplifications,
and educational readability.
