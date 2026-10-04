# Phase 4: BBR sender transport

## Scope and reference

Accepted pre-task Python revision:
`9659756664a031317558a3b9817f5f2449c76bc1`. Days revision:
`9ff20eac16dcdf752510b05cbcf526684dc05146` at
`/Users/bli/Playground/days`.

The current CPU backend delegates TCP transitions to
`executor/src/scalar.rs`; inspection of ACK and retransmission transitions around
lines 3390–3470 and 3560–3600 informed shared byte/timer/recovery invariants.
Current Days CPU has no BBR sender. These are independent transport observations,
not a CPU BBR equivalence claim. Days clamps excessive ACKs to its emitted
frontier; this sender ignores malformed or excessive external ACKs entirely.

Changes stay in `ns/packet/bbr_generator.py`, its two packet test suites, and a
precise consumed-marker correction in `ns/packet/rate_sample.py`. The latter had
CRLF line endings; it is normalized to LF. Its only behavioral changes replace
`delivered_time == 0` / assignment to zero with a `None` consumed marker, so a
packet sent at simulation time zero is counted exactly once. No BBR controller
or general Flow application helper rewrite is included.

## Transport behavior

- The controller's MSS determines segmentation. Sequences, outstanding ranges,
  final tails and congestion-window admission use whole bytes. Finite application
  write sizes of at least one byte are floored once; nonpositive, subbyte or
  nonfinite chunks and nonpositive/nonfinite arrival intervals are rejected.
- Finite bulk transfers buffer their full declared volume; an unlimited bulk
  flow (`size=None`) supplies another MSS as needed. Nonbulk writes keep one
  arrival draw until its scheduled time, respect the declared byte cap, and do
  not call the Flow helper that redraws arrivals on each poll. Missing nonbulk
  distributions default to MSS writes separated by the configured granularity.
- `start_time` is absolute. `finish_time` is an exclusive deadline for accepting
  and emitting new data; it is rechecked after pacing, application and window
  waits. `None` imposes no deadline. Bytes already emitted retain their timer
  and may retransmit and drain after the deadline.
- Only integer ACK frontiers for `10000 + flow.fid`, from the current cumulative
  frontier through the emitted frontier, affect the sender. Stale, unrelated,
  malformed and excessive ACKs are ignored. Duplicate ACKs never fabricate
  delivery or RTT samples. Advancing ACKs remove exactly their newly covered
  bytes, including an interior partial segment; its remaining suffix is the
  next retransmission range.
- Every send and retransmission is a fresh Packet. Logical segment state owns
  transport timestamps and BBR sampling snapshots. `Packet.time` remains the
  first transmission time for latency accounting. Sampling consumes a local
  packet copy, so queue/receiver packet objects retain their metadata.
- Flight counts unique unacknowledged bytes and does not increase on
  retransmission. Zero-time sends and partially acknowledged ranges are counted
  without using delivery timestamps as an accounting sentinel. BBR receives
  post-ACK flight; classic TCP's separate controller contract receives pre-ACK
  flight when computing loss-window adjustments.
- One timer tracks the oldest outstanding range. Advancing ACKs restart it from
  ACK processing time; ordinary duplicate ACKs do not. Initial/learned RTO is
  bounded to 1–60 seconds, backoff caps at 60, and default clock granularity is
  1 ms. RTT samples use sender state for exactly one complete unretransmitted
  segment; cumulative, partial and retransmission ACKs remain ambiguous without
  timestamps/SACK. RTTVAR uses the previous SRTT and absolute deviation.
- The third duplicate ACK retransmits once. Further duplicates notify the
  controller without resending the same hole. A partial recovery ACK retransmits
  the next missing range; recovery persists to its saved flight frontier.
- Byte accounting and timer state are committed before synchronous forwarding,
  both for new data and retransmissions. An immediate ACK may safely finish the
  flow and cancel its timer. Completion produces no subsequent retransmissions.
  ACK wakeups are coalesced instead of retaining one token per ACK.

BBR pacing remains in bytes/second: sending `size` bytes postpones the next new
send by `size / pacing_rate`. Retransmissions retain their existing immediate
transport behavior. Congestion-control transitions, recovery-window math and the
full delivery-rate estimator remain Phase 5 work. The sender suppresses division
by a zero sampling interval for synchronous ACKs; estimator sampling/filter
validity and its RTT constraints are not claimed complete by this task.

## Red and green evidence

The first finite-deadline reproducer selection produced 14 failures before the
rewrite. After adding a direct zero-time sampler regression, the final tests can
be rerun against accepted modules without changing the worktree:

```sh
uv run --locked python - <<'PY'
import importlib
import subprocess
import pytest
for name in ('ns.packet.bbr_generator', 'ns.packet.rate_sample'):
    module = importlib.import_module(name)
    path = name.replace('.', '/') + '.py'
    source = subprocess.check_output(
        ['git', 'show', f'9659756:{path}'], text=True,
    )
    exec(compile(source, f'9659756/{path}', 'exec'), module.__dict__)
raise SystemExit(pytest.main([
    '-q', '--tb=no', 'tests/packet/test_bbr_transport.py', '-k',
    'controller_mss or invalid_ack or partial_ack_frees or zero_time_flight '
    'or third_duplicate or timer_restarts or rtt_comes or synchronous_ack '
    'or exclusive_deadline or rate_sampler_counts',
]))
PY
```

Observed: **15 failed, 17 deselected**. Failures cover MSS/fractional admission,
wrong-flow and malformed ACKs, partial ACK flight, time-zero delivery, two-ACK
fast retransmission, oldest-timer restart origin, trusting an echoed RTT,
synchronous completion, deadline overshoot and the consumed sampling marker.
The unlimited-flow baseline independently failed because `finish_time=None`
was compared numerically and its initial send buffer was `None`.

```sh
uv run --locked pytest -q tests/packet/test_bbr_generator.py \
  tests/packet/test_bbr_transport.py tests/flow/test_bbrv3.py \
  tests/flow/test_bbrv3_integration.py
```

Observed: **45 passed**. Tests exercise actual process sends and timers; the old
fabricated packet-state fallback and DummyTimer tests were removed. Additional
checks cover one data loss or ACK loss followed by post-deadline drain, short
application tails, whole-byte application quantization, invalid arrivals,
absolute start time, preserved rate metadata, and pacing timestamps at
0/0.1/0.2 seconds for sizes 300/300/100 and rate 3000 bytes/s.

Both ACK-first and timeout-first insertions at the same timestamp are tested.
SimPy's insertion order determines whether one attempt retransmits. Either order
leaves the sender drained with no live retransmission timer. This documents the
known boundary difference from Days' arrival-before-timeout phases rather than
changing global SimPy ordering.

A shared-tree regression run during this task produced **306 passed** before the
last timer alignment/test cleanup. The phase integrator records final merged
regression, examples and package checks separately. `git diff --check` passes.

## Line counts and readability

Physical categories follow Phase 0: nonblank docstrings/comment-only lines are
explanatory; all other nonblank lines are code-bearing, including delimiters.
These are a size/readability proxy rather than executable-statement counts.

| Owned production | Accepted | Candidate | Change |
| --- | ---: | ---: | ---: |
| Physical lines | 565 | 522 | -43 |
| Code-bearing lines | 424 | 408 | -16 |
| Explanatory lines | 68 | 76 | +8 |
| Blank lines | 73 | 38 | -35 |
| Inline comments (overlap code) | 5 | 3 | -2 |

The BBR sender alone changes from 444 to 400 physical lines, 335 to 319
code-bearing lines, and 48 to 55 explanatory lines. Sampler code-bearing lines
remain 89, with one additional explanatory line. The two sender test files total
556 physical lines, 455 code-bearing, two explanatory and 99 blank, versus the
previous single file's 361/297/2/62. The implementation retains recognizable
SimPy `run()`, `put()` and timer callbacks; no execution or configuration
framework is introduced.

## Review fix: bounded synchronous recovery stack

Review of candidate `9466d4fe4a305c6fade7290deb7e95588054e96f` identified a
synchronous partial-recovery ACK chain that exceeded Python's recursion limit.
The regression uses `Flow(fid=7, size=65536, finish_time=1)`, real
`BBR(mss=128, cwnd=65536)`, a direct TCPSink ACK path, and loss of the first
attempt of every segment beginning below byte 65152. The final three original
segments generate fast retransmit; 509 consecutive holes then need recovery.

Only retransmission triggered by a partial recovery ACK is deferred to a new
SimPy turn via `timeout(0)`. This preserves simulation time and prevents nested
`put()` calls from growing with the loss burst. The process captures the range's
sequence and attempt count; before emitting, it confirms the same range remains
at the ACK frontier, recovery remains active, and another attempt has not
superseded it. Only then are loss/attempt metadata and the timer committed before
synchronous forwarding. An intervening cumulative ACK, interior partial ACK, or
timeout safely cancels the obsolete deferred action. Initial fast retransmit and
timeout forwarding retain their existing synchronous behavior.

The new tests against the reviewed candidate are reproducible without changing
the worktree:

```sh
uv run --locked python - <<'PY'
import importlib
import subprocess
import pytest
module = importlib.import_module('ns.packet.bbr_generator')
source = subprocess.check_output([
    'git', 'show', '9466d4f:ns/packet/bbr_generator.py',
], text=True)
exec(compile(source, '9466d4f/bbr_generator.py', 'exec'), module.__dict__)
raise SystemExit(pytest.main([
    '-q', '--tb=no', 'tests/packet/test_bbr_transport.py', '-k',
    'synchronous_burst_loss or retire_a_deferred',
]))
PY
```

Observed red: **2 failed, 34 deselected**. The burst case raises RecursionError;
the retirement case emits a retransmission before a subsequent covering ACK can
retire it. On the fixed sender, the original focused command above produces
**49 passed**. The burst drains exactly 65536 bytes with each lost segment sent
exactly twice and each remaining segment once. Continued simulation through
five seconds produces no additional attempt and leaves no timer or outstanding
range. Further tests check a pending range trimmed by an interior ACK and a
pending attempt superseded by timeout. `git diff --check` passes.

Compared with the reviewed candidate, this repair adds nine code-bearing lines,
four explanatory lines and one blank line to production. The table above records
the complete resulting source totals against the accepted pre-phase revision.
