# Phase 3 Virtual Clock audit

Implemented against accepted Phase 2 revision
`5db0fad693e92690e5928357ab0e2b87c38604c1` on 2026-10-03. Scope:
`ns/scheduler/virtual_clock.py` and `tests/scheduler/test_virtual_clock.py`.
The orchestrator records the exact candidate commit and task review after its
snapshot. This task is ready for bounded algorithm review; shared-buffer identity
and mapped-class monitor changes remain assigned to the composition task.

## Algorithm and reference contract

Current Days CPU has no Virtual Clock scheduler. These are independent algorithm
tests, not a CPU equivalence claim. The primary reference is the checked-in
[Zhang paper](../docs/references/virtual_clock.pdf), section 3.1, printed page 107
(PDF page 7). This file is the 1991 TOCS expanded paper, rather than the 1990
SIGCOMM publication formerly cited in the Python module. The Python citation now
identifies the paper actually inspected. At pinned Days revision
`9ff20eac16dcdf752510b05cbcf526684dc05146`,
`legacy/src/schedulers/vc.rs::tag` is a secondary corroboration of the size-aware
clock increment. No legacy scheduler output is used as a fixture.

The scheduler's supported subset is the data-forwarding rule, with an unlimited
queue. It does not implement the paper's AR/AI observation interval, source
feedback, periodic synchronization between its two clocks, or buffer-overflow
policy. The retained `v_clocks` expose the cumulative monitoring clock; they are
not a complete rate monitor. These limits are stated in the class docstring.

- Packet sizes are bytes, link rates bits/second, vticks seconds/bit, and clocks
  seconds. Both clocks advance by `packet.size * 8 * vtick`, the requested service
  time at the class's reserved rate. The previous scheduling clock advanced by
  vtick alone, which changed the order for variable-size packets.
- The first arrival initializes the monitoring clock to that arrival's simulation
  time. Membership in observed-class accounting replaces the ambiguous zero-clock
  sentinel. Later arrivals retain the cumulative clock. The scheduling clock is
  floored at each arrival's real time, then incremented by requested service time.
  A clock still ahead of real time survives an empty physical queue. Idle time
  earns no scheduling credit. Packet generation time is not queue arrival time.
- Class mapping selects one shared history for all flows in that class. Lists and
  dictionaries retain their existing constructor conventions. Positive finite
  vticks are required; missing class IDs fail before modifying admission counters.
- Tags rank packets; they do not impose transmission deadlines. Service starts
  whenever work is available and remains nonpreemptive. At each service start,
  the smallest waiting tag wins. TaggedStore's insertion counter preserves FIFO
  admission order for equal tags without comparing packet objects.
- The process waits on a local event when idle, instead of leaving a pending heap
  get that could reserve the first arrival too early. A zero-time wait before
  selection includes already scheduled same-time arrivals, including a later
  inserted arrival timeout at a service completion. This local convention does
  not reproduce Days' global phase ordering for arbitrarily long event chains.
- Queue packet and byte counters exclude service from its start and exclude
  packets retained after service for downstream backpressure. The currently
  serializing packet is reported separately and cleared before synchronous
  upstream callbacks or `out.put()`.
- Optional upstream hooks can be absent in zero-buffer mode. With hooks, release
  happens at local completion for ordinary forwarding, or at downstream pull for
  a retained handoff. Each tested handoff forwards the original packet object,
  invokes its callback once, and removes its hook bookkeeping.

## Independent expected observations

All link tests use 800 bits/second: 100 bytes take exactly one second.

| Scenario | Hand-derived observation |
| --- | --- |
| 1000 bytes at vtick 1/8000; 100 bytes at 1/4000; both at time 0 | Tags 1 and 0.2 seconds; small then large; departures at 1 and 11 seconds |
| Class a: 500 then 100 bytes from distinct flows; class b: 900 bytes; vticks 1/8000 | Tags 0.5, 0.6, 0.9; class-a packets precede b; departures at 5, 6, 15 |
| 100, 200, 50 bytes at vticks 1/800, 1/1600, 1/400 | Three tags equal 1; admission order; departures at 1, 3, 3.5 |
| 1000 and 500 bytes arrive at 5; 250 bytes at 30; vtick 1/8000 | Departures at 15, 20, 32.5; cumulative clock 6.75; auxiliary clock 30.25 |
| 100 bytes at 0, then 50 bytes after idle until 2; vtick 1/8 | Tags 100 and 150 despite idle physical queue; departures at 1 and 2.5 |
| A small-tag packet arrives during current service or exactly at completion | Current packet completes; the newly eligible smaller tag wins the next selection |
| 100-byte packet serializing with 40 bytes waiting | Waiting telemetry is 1 packet/40 bytes; service-inclusive monitor is 2 packets/140 bytes |

Additional tests cover an idle wakeup with a later same-time arrival, future tags
without shaping, synchronous reentrant forwarding, downstream-retained storage,
callback timing, standalone zero-buffer input, invalid vticks, and missing-class
admission without partial state changes.

## Red and green checks

The initial tests preceded production edits and produced **19 failed, 3 passed**.
Strengthening the idle wakeup case then produced an independent failing
reproducer. Replaying the final test file against the pre-task production module
produced **20 failed, 2 passed** (0.02 seconds). This replay alters only the module
loaded in that Python process, leaving the worktree untouched:

```sh
uv run --locked python - <<'PY'
import subprocess
import ns.scheduler.virtual_clock as virtual_clock
import pytest

baseline = subprocess.check_output([
    'git', 'show', '5db0fad:ns/scheduler/virtual_clock.py'
])
exec(compile(baseline, '<pre-task VirtualClockServer>', 'exec'),
     virtual_clock.__dict__)
raise SystemExit(pytest.main([
    '-q', '--tb=no', 'tests/scheduler/test_virtual_clock.py'
]))
PY
```

After repairs:

- `uv run --locked pytest -q tests/scheduler/test_virtual_clock.py tests/scheduler/test_servers.py -k 'virtual_clock'`:
  **24 passed, 11 deselected** (0.02 seconds).
- `uv run --locked pytest -q --ignore=tests/scheduler/test_wfq.py --ignore=tests/scheduler/test_sp.py`:
  **154 passed** (0.15 seconds) in the current shared worktree. Paused scheduler
  files were excluded; this is a bounded regression run, not the Phase 3 gate.
- `git diff --check -- ns/scheduler/virtual_clock.py`: passed.
- The existing example ran via `runpy.run_path` with `MPLBACKEND=Agg` from a
  disposable temporary directory. It admitted 52 packets, delivered 29 flow-0
  and 23 flow-1 packets, emptied both waiting queues, and generated its plot. The
  plot was deleted with the temporary directory. Agg's expected noninteractive
  `plt.show()` warning did not prevent completion. Reproduction command:

```sh
MPLBACKEND=Agg uv run --locked python - <<'PY'
from pathlib import Path
import os
import runpy
import tempfile

example = Path('examples/virtual_clock.py').resolve()
with tempfile.TemporaryDirectory(prefix='ns-vc-example-') as workspace:
    os.chdir(workspace)
    runpy.run_path(str(example))
PY
```

## Composition follow-up

The existing zero-buffer release code calls an unconditional upstream `get()`.
If Virtual Clock reorders packets held in an upstream FIFO, that get removes the
wrong identity. A two-packet observation confirmed callback packet ID 1 while
the upstream queue still contained packet ID 1, because packet ID 0 had been
removed instead. This task deliberately adds no scheduler-specific helper;
the composition task owns the shared exact-identity repair and its regression.
The callback tests here use one packet so they establish timing without hiding
or claiming to close the identity issue.

`ServerMonitor` currently compares the active packet's `flow_id` with queue IDs.
It therefore fails to add service for a mapped class whose ID differs from the
flow ID. This task establishes correct class-based waiting counters and tests
service inclusion with the default mapping; the composition task owns mapped
class monitor integration.

## Size and readability

Physical-line categories follow Phase 0's AST/tokenize definition. Nonblank
docstring and comment-only lines are explanatory; other nonblank lines are
code-bearing, a proxy rather than an executable-statement count. Inline comments
are counted separately and overlap code-bearing lines.

| File | Physical before → after | Code-bearing before → after | Explanatory before → after | Blank before → after |
| --- | ---: | ---: | ---: | ---: |
| `ns/scheduler/virtual_clock.py` | 234 → 242 (+8) | 126 → 125 (-1) | 70 → 80 (+10) | 38 → 37 (-1) |
| New test file | 0 → 286 | 0 → 219 | 0 → 12 | 0 → 55 |

Production inline comments remain zero. The loop shares ordinary/retained
serialization instead of duplicating it, class lookup is named once per method,
and the only new scheduling state is a local wakeup event. Comments explain tag
units, both clock roles, selection timing, nonpreemption, queue telemetry, and
the supported subset of the paper. No engine, framework, dependency, or common
scheduler abstraction was added.
