# Phase 4 receiver and transport integration evidence

The Phase 4 baseline is the accepted Phase 3 tree `9659756`. This task owns
`ns/packet/tcp_sink.py`, `tests/packet/test_tcp_sink.py`,
`tests/packet/test_tcp_transport_integration.py`, and `docs/tcp_timing.md`.
The integration suite has a distinct basename from the existing flow integration
suite so default pytest import collection remains valid.

## Receiver audit and red/green result

The receiver's sorted interval merging and contiguous-prefix ACK calculation
already handle adjacency, overlapping ranges, nested duplicates, and gaps.
They were retained, with the misleading priority-queue, advertised-window, and
future RTT rewrite comments corrected. One sink represents one connection.

`bytes_delivered` is a read-only view of `next_seq_expected`, so the teaching API
does not duplicate mutable state. Inherited PacketSink counters remain physical
arrival accounting. In the receiver accounting test, arrival sizes 100, 100,
150, and 100 total 450 physical bytes; delivery progresses 0, 0, 200, 200 bytes.
The out-of-order duplicate contributes no contiguous delivery, and filling the
hole releases the buffered prefix exactly once.

Before adding the property:

```text
uv run --locked pytest -q tests/packet/test_tcp_sink.py
1 failed, 5 passed
AttributeError: 'TCPSink' object has no attribute 'bytes_delivered'
```

The five passing cases include the already-correct gap/overlap audit and ACK
metadata echo. After adding the property, the same command gave **6 passed**.
This is an accounting/API clarification; no receiver ACK algorithm defect is
claimed or fabricated. ACK metadata is echoed without mutating the data attempt.

## Independent end-to-end cases

All nine scenarios run separately against both sender types with a passive
controller, a real TCPSink, and explicit per-attempt delivery schedules:

- MSS 300 and 701-byte volume: data sizes 300, 300, 101; reordered/duplicated
  arrivals ACK 0, 0, 600, 701. Physical bytes total 1001, unique delivery 701.
- Drop the middle 300-byte range of a 601-byte flow. ACKs are 300, 300, 601;
  retransmission occurs at 1.02 seconds after the advancing ACK at 0.02.
  The retransmitted packet is fresh and retains original `Packet.time=0`.
- Drop the sole initial ACK of 123 bytes. Data attempts occur at 0 and 1 second,
  arrival waits are 0.01 and 1.01 seconds, physical bytes total 246, unique
  delivery 123, and Karn sampling retains the backed-off two-second RTO.
- A directly connected receiver ACKs inline with a one-MSS window, including
  the short final segment, and cancels registered new-send timer state.
- Receiver ACK and timeout at exactly one second, with both insertion orders:
  ACK first sends one attempt; timer first sends two. Both complete and stop.
- With cwnd 300 and a lost first segment, an exclusive finish at 0.5 seconds
  prevents the unsent suffix, while already emitted bytes recover at one second.
- An ACK exactly at finish cannot release new bytes.
- An application arrival exactly at finish cannot emit data.

The ACK/timeout test contributes two scenarios in the count above. Each completed
case drains to five seconds and asserts no more physical attempts, no logical
outstanding bytes, and no active timer. Expectations derive from explicit byte
volumes and timing, rather than reproducing sender implementation calculations.

## Phase 3 sender baseline reproduction

To isolate sender failures from the new receiver accounting property, an isolated
`git archive 9659756` checkout received only the current receiver and current
integration test file. The baseline sender implementations remained untouched.
Running the following selection in that checkout gave **6 failed, 12 deselected**:

```text
python -m pytest -q --tb=short tests/packet/test_tcp_transport_integration.py \
  -k 'reorder_duplicate_and_custom_mss_short_tail or data_loss_retransmits_gap or ack_loss_repeats'
```

Both baseline senders emitted 512-byte segments despite the controller MSS 300,
so the custom-MSS and explicit gap-loss expectations failed for both. In ACK loss,
classic TCP retained RTO 1 instead of the expected backed-off 2; BBR retransmitted
at 0.28 seconds instead of the aligned one-second initial RTO. The assertions
identify observable packet sizes/times and timer behavior. Sender repairs belong
to their separate Phase 4 tasks; no sender source was edited by this task.

The isolated reproduction used the repository Python interpreter, extracted a
temporary archive with `tarfile.extractall(filter='data')`, copied those two
files, and invoked pytest with `subprocess.run(..., timeout=3)` before deleting
the task-owned temporary checkout. Normal tests need no archive or reference
checkout.

## Validation

```text
uv run --locked pytest -q tests/packet/test_tcp_sink.py tests/packet/test_tcp_transport_integration.py
24 passed

uv run --locked pytest -q
331 passed

git diff --check
clean
```

These results cover the integrated tree after the two initial sender task commits.
Phase review and later sender fixes require their own integrated revalidation.
The timing note records the actual APIs, including original latency timestamps,
conservative RTT ownership, timer bounds, application deadlines, pacing units,
and the local SimPy/Days ACK-timeout ordering difference. Current Days CPU has
no BBR counterpart; this task makes no new CPU equivalence claim.

## Source growth and educational readability

Compared with `9659756`, physical Python lines are classified as executable/code,
explanatory (docstrings and full-line comments), or blank. Inline comments remain
on their code line. AST docstring ranges identify explanatory lines consistently.

| File | Code before → after | Explanatory before → after | Blank before → after |
| --- | --- | --- | --- |
| `ns/packet/tcp_sink.py` | 53 → 56 (+3) | 20 → 21 (+1) | 14 → 16 (+2) |
| `tests/packet/test_tcp_sink.py` | 50 → 96 (+46) | 0 → 2 (+2) | 23 → 34 (+11) |
| `tests/packet/test_tcp_transport_integration.py` | 0 → 206 (+206) | 0 → 12 (+12) | 0 → 48 (+48) |

Production growth is three code lines for the property; the receiver's simple
interval representation remains recognizable. Test growth supplies independent
scheduled observations for both senders. The timing note replaces 24 lines with
the complete transport contract, with no new execution framework or abstraction.
