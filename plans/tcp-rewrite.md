# TCP Rewrite Plan

## Goal

Bring `ns.py`'s TCP implementation materially closer to defensible TCP behavior,
fix Issue `#34` for the right reason, and remove the current transport-level
semantic errors around cumulative ACK handling, retransmission object reuse,
tail-segment sending, and RTT/RTO measurement.

This plan does not cut scope. It includes:

- classic TCP receiver correctness
- classic TCP sender correctness
- conservative Karn/Partridge RTT handling
- documentation and regression coverage
- BBR timing/metadata alignment as a follow-on phase in the same rewrite plan

## Current Problems

1. `ns/packet/tcp_sink.py` ACKs past holes because it derives the next ACK from
   the first merged interval's end instead of the current cumulative frontier.
2. `ns/packet/tcp_generator.py` stores and retransmits the same `Packet`
   object, which causes attempt-local state and end-to-end timing to alias.
3. `Packet.time` is currently used by sinks for wait/latency accounting, so
   mutating it on retransmit corrupts the observed latency.
4. RTT/RTO sampling currently depends on receiver-echoed packet timing instead
   of sender-owned segment metadata.
5. ACK cleanup currently assumes fixed-MSS behavior and uses `seq < ack`
   semantics instead of `seq + len <= ack`.
6. All send paths assume full-MSS sends, which breaks buffered sub-MSS chunks
   and tail segments.
7. Python BBR has the same timestamp/object reuse problem, but with additional
   rate-sample and timer coupling.

## Design Invariants

These invariants should be locked before code changes.

1. `Packet.time` on TCP data packets remains the original first-transmit
   timestamp used by sinks for end-to-end wait/latency accounting.
2. Sender timing and retransmission state live in sender-owned logical segment
   state, not in mutable packet objects.
3. Receiver ACK is the cumulative frontier: the next expected byte
   (`RCV.NXT`), based only on the contiguous prefix.
4. Segment cleanup uses `seq + size <= ack`.
5. Every send or retransmit emits a fresh `Packet` object derived from segment
   state.
6. RTT estimation uses sender-side metadata only.
7. RTT updates must be conservative in the absence of TCP timestamps, SACK, and
   delayed-ACK modeling.

## Non-Goals

This rewrite does not include:

- SYN/FIN state machine support
- TCP timestamps option
- SACK
- delayed ACK policies
- window scaling
- timer-architecture redesign beyond what is needed to preserve per-segment
  correctness

## Tasks

### R0. Define invariants and implementation boundaries

- `id`: `R0`
- `depends_on`: `[]`

Write down and enforce the transport invariants listed above before editing the
sender or receiver logic. This includes agreeing that:

- `Packet.time` is not the retransmit-attempt timestamp
- sender-owned `SegmentState` is the durable source of truth
- ACK cleanup is based on segment end
- conservative Karn/Partridge behavior is mandatory in phase 1

Acceptance criteria:

- the timing contract is explicit in code comments or docs where ambiguity is
  currently causing bugs
- all later tasks use the same field semantics consistently

### R1. Add receiver red tests for cumulative ACK semantics

- `id`: `R1`
- `depends_on`: `["R0"]`

Add focused tests for `ns/packet/tcp_sink.py` that cover:

- first packet arrives out of order and ACK stays pinned at current `RCV.NXT`
- duplicate arrival of already-buffered data does not advance ACK
- hole-fill causes ACK jump across the now-contiguous prefix
- merged receive intervals remain correct after reorder, duplicate, and fill

Acceptance criteria:

- tests fail on the current implementation
- tests describe cumulative ACK behavior clearly enough to drive the receiver fix

### R2. Add sender red tests for classic TCP transport semantics

- `id`: `R2`
- `depends_on`: `["R0"]`

Add tests for `ns/packet/tcp_generator.py` covering:

- fast retransmit must not reduce sink-observed latency
- timeout retransmit must not reduce sink-observed latency
- buffered sub-MSS data must be sent
- final tail segment must be sent and cumulatively acknowledged
- ACK cleanup uses segment end, not segment start
- ACKs that cover retransmitted data must not update the RTT estimator
- sender emits fresh packet objects per attempt instead of mutating one object

Acceptance criteria:

- tests fail on the current implementation
- tests cover both duplicate-ACK and timeout retransmission paths separately

### R3. Fix receiver cumulative ACK behavior

- `id`: `R3`
- `depends_on`: `["R1"]`

Refactor `ns/packet/tcp_sink.py` so cumulative ACK computation is based on the
current frontier, not the first merged interval's end.

Implementation shape:

1. keep merged receive intervals if they remain the simplest representation
2. start from current `RCV.NXT`
3. advance the frontier only while an interval begins at or before the current
   frontier
4. stop at the first gap

Acceptance criteria:

- all `R1` tests pass
- out-of-order arrivals generate duplicate ACK behavior that matches the pinned
  cumulative frontier

### R4. Refactor classic sender around logical segment state

- `id`: `R4`
- `depends_on`: `["R2", "R3"]`

Refactor `ns/packet/tcp_generator.py` so the sender owns durable logical
segment state keyed by starting sequence number.

`SegmentState` should capture at least:

- `seq`
- `size`
- `first_tx_time`
- `last_tx_time`
- `retransmit_count`
- timer state / backoff state

Behavioral changes:

- every send and retransmit emits a fresh `Packet`
- emitted packets inherit `packet_id` and `size` from the logical segment
- emitted packets use `Packet.time = first_tx_time`
- timer ownership stays with logical segment state, not packet objects
- ACK cleanup uses `seq + size <= ack`
- all send paths compute `sendable_bytes = min(mss, available)` instead of
  assuming full MSS

This task must cover:

- normal send path
- timeout retransmit path
- duplicate-ACK retransmit path
- duplicate-ACK `> 3` new-data path
- short/tail segment sending

Acceptance criteria:

- all `R2` tests except RTT-estimator-specific tests pass
- packet aliasing between attempts is gone
- tail and buffered sub-MSS sends work in all sender paths

### R5. Fix classic RTT/RTO measurement conservatively

- `id`: `R5`
- `depends_on`: `["R4"]`

Move RTT/RTO sampling fully onto sender metadata. Do not use receiver-echoed
`ack.time` as the RTT oracle.

Phase-1 conservative eligibility rule:

- update `SRTT`, `RTTVAR`, and `RTO` only when an ACK advances by exactly one
  logical segment and that segment has `retransmit_count == 0`
- skip RTT updates on cumulative jumps
- skip RTT updates on ACKs that newly cover retransmitted data
- skip RTT updates on ambiguous recovery ACKs

When an ACK is ambiguous:

- still process the ACK for congestion control
- pass the current `smoothed_rtt` or last valid RTT sample into the congestion
  control callback instead of an ambiguous fresh measurement

Keep:

- RFC 6298 update ordering
- timeout backoff behavior
- existing congestion-control event flow, unless a callback contract change is
  required to separate ACK advancement from RTT estimator updates

Acceptance criteria:

- RTT-estimator tests from `R2` pass
- no RTT update occurs on ambiguous retransmission-related ACKs
- RTO backoff remains correct on timeouts

### R6. Document classic TCP timing semantics

- `id`: `R6`
- `depends_on`: `["R5"]`

Add a short timing/transport note documenting:

- cumulative ACK semantics
- sender-owned logical segment state
- fresh packet per attempt
- `Packet.time` as first-transmit time for sink latency accounting
- sender-only RTT/RTO measurement
- conservative no-timestamps/no-SACK assumptions in this phase

Acceptance criteria:

- the timing contract is discoverable without re-reading the entire sender
- comments/docs prevent reintroduction of timestamp-reset regressions

### R7. Align BBR timing and metadata with the new sender contract

- `id`: `R7`
- `depends_on`: `["R4", "R5"]`

Refactor `ns/packet/bbr_generator.py` to remove packet-object reuse and align
attempt timing with sender-owned state.

This phase must include:

- fresh packet per send/retransmit
- no mutation of data-packet `Packet.time` for retransmit-attempt timing
- sender-owned attempt timing for timer handling
- sender-owned metadata feeding BBR rate-sample inputs
- review of ACK cleanup assumptions that currently step by `mss`
- re-validation of timeout restart behavior and delivery-rate bookkeeping after
  the timing contract changes

This phase should not blindly copy classic TCP's RTT estimator rules where BBR
has distinct sampling requirements, but it must obey the same object/timestamp
ownership model.

Acceptance criteria:

- BBR no longer corrupts end-to-end latency by mutating packet timestamps
- BBR no longer relies on packet-object reuse to carry sender state
- BBR regression tests cover both duplicate-ACK and timeout retransmit timing

### R8. Add BBR red/green regression coverage

- `id`: `R8`
- `depends_on`: `["R7"]`

Expand test coverage for `ns/packet/bbr_generator.py` so the BBR rewrite is
validated rather than assumed correct.

Cover at least:

- duplicate-ACK retransmit latency behavior
- timeout retransmit latency behavior
- fresh packet per attempt behavior
- ACK cleanup with short segments where applicable
- rate-sample stability after retransmission timing changes

Acceptance criteria:

- BBR-specific timing regressions are locked down with deterministic tests

### R9. Run examples and end-to-end validation

- `id`: `R9`
- `depends_on`: `["R6", "R8"]`

Validate the rewritten transport paths with both unit/regression tests and
example-level runs.

Validation set:

- `uv run pytest -q`
- focused TCP/BBR tests added in this rewrite
- `uv run python examples/tcp.py`
- any existing BBR example or integration path that exercises the sender/receiver loop

Acceptance criteria:

- classic TCP regression suite passes
- BBR regression suite passes
- example behavior remains functional and does not regress obvious transport flow

## Dependency Graph

```text
R0 -> R1
R0 -> R2
R1 -> R3
R2 -> R4
R3 -> R4
R4 -> R5
R5 -> R6
R4 -> R7
R5 -> R7
R7 -> R8
R6 -> R9
R8 -> R9
```

## Implementation Notes

1. Do not treat the Rust sink as a semantic oracle for cumulative ACK behavior.
   The Rust sender has useful structural ideas; the Rust sink has the same
   simplification around contiguous-frontier derivation.
2. The safest first-pass RTT policy is deliberately conservative. Without TCP
   timestamps, ambiguous ACK attribution should be skipped rather than guessed.
3. The ACK cleanup rule must become segment-end-based before short segments are
   introduced broadly; otherwise tail handling and retransmission cleanup will
   remain subtly wrong.
4. This rewrite should prefer the smallest maintainable sender-state abstraction
   that separates logical segment state from emitted packet objects. It does not
   need a large transport architecture overhaul.

## Deliverables

By the end of this plan, the codebase should have:

- correct cumulative ACK frontier handling in the TCP sink
- fresh packet-per-attempt behavior in classic TCP and BBR
- stable end-to-end latency accounting across retransmissions
- conservative sender-owned RTT/RTO measurement for classic TCP
- generic short-segment send support across all sender paths
- explicit transport-timing documentation
- regression tests covering both classic TCP and BBR timing semantics
