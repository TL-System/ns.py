# Phase 2 utility audit

Implemented against accepted Phase 1 revision `807c35d` on 2026-10-03. Scope:
`ns/utils/timer.py`, `taggedstore.py`, and `delayer.py`, with independent behavior
tests in `tests/utils/`. Candidate commit and task-review acceptance are recorded
by the orchestrator after its snapshot.

## Contracts and repairs

- Timer timeouts and absolute start times use simulation seconds. Expiration is
  one-shot unless the callback explicitly calls `restart()`. Previously, a
  callback that did not stop/restart repeated without a yield at the same time.
  The reproducer raises on the second callback, so the red test cannot hang.
- External restart now interrupts the old wait, supporting earlier and later
  deadlines; cancellation wakes the process so it finishes promptly. Restart
  rearms both stopped and expired timers, including stop/restart before the
  next process turn. Callback restart retains the same timer object and avoids
  interrupting its own process, as required by existing TCP callers.
- `restart(rto)` starts at the current time. `restart(rto, start_time=0)` now
  means absolute time zero; the old zero sentinel could discard an original
  TCP transmission timestamp. An already-passed deadline yields a zero timeout
  and expires at the current simulation time. RTOs must be finite/nonnegative,
  and explicit start times finite; invalid restart leaves the old timer armed.
- Delayer samples one arrival-based deadline in seconds per packet, and retains
  FIFO when later deadlines are earlier. It forwards the original packet object;
  the old shallow copy silently changed object identity while sharing mutable
  nested metadata. A single SimPy Store now carries queued work and supplies the
  idle wakeup, removing the duplicate waiting/wake-token bookkeeping.
- StackDelayer retains its established **bytes/second** processing-speed API:
  `packet.size / speed` seconds, with no factor of eight. A 100-byte packet and
  50-byte packet at 100 bytes/second depart at 1 and 1.5 seconds. After idle until
  time 2, 25 bytes depart at 2.25. Positive infinity permits zero processing
  delay, and the process still yields. Nonpositive/NaN speeds are rejected.
- `waiting_queue` remains an inspection alias for each delayer's Store items;
  it contains waiting packets rather than the packet currently being processed.
  `put()` and `out.put()` composition and constructor conventions are retained.
- TaggedStore already ordered equal tags stably without comparing packet
  contents. Tests cover lowest-tag selection, equal-tag FIFO, bounded capacity,
  pending-put cancellation, and an idle get. Its docs now describe tagged
  ordering rather than unconditional FIFO; the insertion counter counts actual
  admissions. NaN capacity is rejected instead of leaving every put blocked.

SimPy interrupt cancellation detaches the timer process from its timeout; the
old timeout event itself may still remain in the environment's event queue and
advance an unbounded `env.run()` clock. It cannot trigger a callback. Equal-time
events retain SimPy ordering; this task adds no event engine or global phase
ordering. The generic store/delayers have no direct current Days CPU counterpart;
their acceptance uses the explicit independent invariants above. The separate
Phase 2 FIFO reference task owns the actual Days CPU comparison.

## Red and green checks

The initial 31 utility tests were written before behavior changes. Running
`uv run --locked pytest -q tests/utils/test_timer.py tests/utils/test_taggedstore.py tests/utils/test_delayer.py`
against the unchanged utilities produced **23 failed, 8 passed** (0.09 seconds).
The failures exposed callback repetition, stale restart deadlines, cancellation
lifetime, rearming, zero start time, elapsed deadlines, packet copies, and invalid
configuration. Callback restart, zero-time yielding, and normal tagged ordering
already passed.

After the fixes and five additional boundary cases, the same command produced
**36 passed** (0.04 seconds). Transport compatibility was checked with
`uv run --locked pytest -q tests/packet/test_tcp_generator.py tests/packet/test_bbr_generator.py tests/packet/test_tcp_sink.py`:
**18 passed** (0.02 seconds). `git diff --check` passed.

The final test set was also replayed against the original three utility modules
from `807c35d`, copied to a disposable directory with only their import paths
changed. It produced **26 failed, 10 passed** (0.05 seconds), including rejection
of infinite RTO and invalid explicit start times. This command reproduces that
red run without modifying the worktree:

```sh
uv run --locked python - <<'PY'
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix='ns-utility-red-') as work:
    work = Path(work)
    for name in ('timer', 'taggedstore', 'delayer'):
        baseline = subprocess.check_output(
            ['git', 'show', f'807c35d:ns/utils/{name}.py'], text=True
        )
        (work / f'legacy_{name}.py').write_text(baseline)
        tests = Path(f'tests/utils/test_{name}.py').read_text()
        tests = tests.replace(f'from ns.utils.{name} import', f'from legacy_{name} import')
        (work / f'test_{name}.py').write_text(tests)
    result = subprocess.run([
        sys.executable, '-m', 'pytest', '-q', '--tb=no',
        *(str(work / f'test_{name}.py') for name in ('timer', 'taggedstore', 'delayer')),
    ])
    raise SystemExit(result.returncode)
PY
```

## Size and readability

Physical-line categories use the Phase 0 AST/tokenize definition: nonblank
docstrings and comment-only lines are explanatory; remaining nonblank lines are
code-bearing (a proxy, not executable-statement counts). Inline comments overlap
code-bearing lines.

| Production module | Physical before → after | Code-bearing before → after | Explanatory before → after | Blank before → after |
| --- | ---: | ---: | ---: | ---: |
| Timer | 59 → 79 | 28 → 41 | 21 → 28 | 10 → 10 |
| TaggedStore | 76 → 78 | 31 → 31 | 25 → 27 | 20 → 20 |
| Delayers | 80 → 80 | 46 → 39 | 22 → 27 | 12 → 14 |
| **Total** | **215 → 237 (+22)** | **105 → 111 (+6)** | **68 → 82 (+14)** | **42 → 44 (+2)** |

Production inline comments remain at three. The three new test files total 403
physical lines: 287 code-bearing, four explanatory, 112 blank. Each changed
process describes its waits. The extra production code is concentrated in timer
lifecycle; the delayer loops are shorter after removing parallel bookkeeping.
No framework, new production abstraction, or dependency was added.
