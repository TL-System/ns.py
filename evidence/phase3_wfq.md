# Phase 3 Days-compatible WFQ audit

Implemented on 2026-10-03 against pre-task revision `cc0905e`. This task owns
`ns/scheduler/wfq.py`, `tests/scheduler/test_wfq.py`, and this evidence. The brief
modernization-plan update records the user's chosen WFQ model and latest
all-subagents `gpt-6.1-sol/high` override. The orchestrator records the exact
candidate commit, fresh task review, and final phase gate after its snapshot.
No commit, publication, or phase approval is implied by these task checks.

## Chosen model and reference

The user explicitly chose to match current Days, using classes with queued plus
in-service packets as the virtual-time active set. This is a packet-active
approximation to fluid GPS; it is not a claim of textbook GPS-based WFQ. The
primary implementation reference is pinned Days revision
`9ff20eac16dcdf752510b05cbcf526684dc05146`,
`executor/src/scalar.rs::{wfq_active_weight_sum,wfq_advance_virtual_time,wfq_enqueue,wfq_complete}`
and `executor/src/model.rs::WfqSchedulerState`. Current CPU uses those transition
rules. The [actual CPU reference evidence](phase3_reference.md) records the
fixture provenance, inputs, commands, and the counterexample between recurrences.
No legacy-only output is represented as a current CPU comparison.

Python retains virtual time and finish tags in seconds. With link rate R in
bits/second, a packet of L bytes in class c receives
`F = max(V, previous_F[c]) + 8*L/R/weight[c]`. While packets are locally active,
virtual time advances by `elapsed_seconds / sum(active_class_weights)`. The
arrival's class joins the active set after its tag is assigned; the in-service
class leaves only after completion advances virtual time using its old weight.
Days scales both V and F by R and uses exact rational work units. This common
positive factor preserves mathematical ranking. Python floating-point rounding
can still distinguish nearly equal tags; tests do not widen timing tolerance to
hide an identity difference.

- The first arrival to an idle server now receives its weighted service
  increment rather than tag zero. When no packet waits or is in service, V and
  all finish histories reset. Idle elapsed time earns no virtual-time credit.
- `active_packets` counts queued plus locally in-service packets by class.
  `flow_queue_count` and `byte_sizes` count only waiting work, removing a packet
  at service start. A downstream-retained packet contributes to neither count
  after local service completes. `total_packets()` sums waiting packets for the
  scheduler telemetry/comparison interface. The current packet is separate.
- Class mapping shares one finish history across flows. Lists and dictionaries
  remain accepted; weights must be nonempty, positive, and finite, and link rate
  must be positive and finite. A missing class, including a negative list class,
  fails before changing admission counters or virtual history.
- Service remains nonpreemptive and starts whenever work is available. At each
  start, the smallest queued tag wins; TaggedStore's insertion counter preserves
  admission order for exact ties. A local wakeup avoids reserving the first idle
  arrival with a pending heap get. A zero-time selection wait includes arrivals
  already scheduled at completion, including a later-inserted arrival timeout.
  This does not reproduce Days' global event phases for arbitrary event chains.
- The original packet object, optional upstream hooks, exact-identity
  `remove_packet()` release, and clearing hooks before callbacks are preserved.
  Service state clears before synchronous forwarding, allowing a callback to
  admit another packet safely. Shared-buffer and mapped-monitor tests exercise
  these paths with the repaired scheduler.

## Independent expected observations

Local tests use 8 bits/second, so one byte takes one second to serialize.

| Scenario | Hand-derived observation |
| --- | --- |
| Idle admission: 8 bytes/weight 1 then 1 byte/weight 8 | Tags 8 and 1/8; second then first; departures 1, 9 seconds |
| Two flows share class a/weight 1; class b/weight 2 | Class-a tags advance 1 then 2; matching class-b tags tie and preserve admission order; departures 1, 3, 4, 6 |
| A busy period drains, then the unequal idle pair arrives at 10 | Fresh tags; departures 1, 11, 19; final V zero and no active classes |
| 8-byte packet in service; class-0 1-byte and class-1 1-byte packets arrive during service or at completion | Current packet finishes at 8; smaller-tag class 1 wins next; departures 8, 9, 10 |
| Sixteen 1-byte packets/weight 8 precede one 1-byte packet/weight 1 | Heavy class's eighth tag ties the light tag at 1 and wins admission tie; light packet is served ninth |
| Initial sizes 10, 100, 13, 14, four unit-weight classes; fifth class sends 10 bytes at 15 | V(15) = 10/4 + 5/3 = 25/6; new tag 85/6 exceeds 14; order 0, 2, 3, 4, 1; departures 10, 23, 37, 47, 147 |
| Initial 4-byte/weight-1 and 30-byte/weight-3 packets; 1 byte/weight 2 arrives at 2 | Initial tags 4, 10; V(2) = 2/4; new tag 1; departures 4, 5, 35 |
| 2-byte packet in service, 1 byte waiting, mapped to one class | Waiting telemetry 1 packet/1 byte; retained ownership after completion leaves waiting and active counters zero |

For the five-class case, fluid GPS would instead give V(15) = 15/4 and a new
tag 55/4, selecting class 4 before class 3. The test deliberately requires the
Days order. That departure order already matched the baseline; it is a semantic
regression guard, not evidence of a newly fixed algorithm defect. The separate
weighted-clock test also guards existing correct active-weight arithmetic.

The CPU tests compare both WFQ fixtures with the actual recorded CPU output,
requiring exact identity order before departure and delivery times. The initial
fixture catches the first-tag bug; the active-clock fixture closes the user's
chosen recurrence contract. These tests are owned by the reference task and use
the same one-femtosecond absolute tolerance as the other integral-nanosecond
scheduler fixtures. No fixture or tolerance changed to fit Python.

## Red and green checks

The preserved initial tests produced **12 failed, 2 passed** before production
changes. Strengthening telemetry, completion selection, reentrant forwarding,
and invalid/missing configuration cases produced **22 failed, 4 passed**.
The final local suite has 27 cases; replay against pre-task production gives
**22 failed, 5 passed** (0.02 seconds):

```sh
uv run --locked python - <<'PY'
import subprocess
import ns.scheduler.wfq as wfq
import pytest

baseline = subprocess.check_output(['git', 'show', 'cc0905e:ns/scheduler/wfq.py'])
exec(compile(baseline, '<pre-task WFQServer>', 'exec'), wfq.__dict__)
raise SystemExit(pytest.main(['-q', '--tb=no', 'tests/scheduler/test_wfq.py']))
PY
```

The replay replaces only the imported module in that Python process; it does
not mutate the worktree. After repairs:

- `uv run --locked pytest -q tests/scheduler/test_wfq.py tests/scheduler/test_days_schedulers.py tests/scheduler/test_composition.py tests/scheduler/test_servers.py`:
  **89 passed** (0.06 seconds).
- `uv run --locked pytest -q`: **245 passed** (0.47 seconds) in the shared
  candidate worktree, with no WFQ exclusions.
- `git diff --check`: passed.
- Existing `examples/wfq.py` and `examples/two_level_wfq.py` ran headlessly in
  temporary directories. The first delivered all **52 packets/52,000 bytes**;
  the second delivered **18 packets/18,000 bytes**. All scheduler queues,
  retained stores, active sets, service state, and upstream hook maps drained.
  The WFQ plot was generated and deleted with its temporary directory. Agg's
  expected noninteractive `plt.show()` warning did not prevent completion.

Reproduce both examples without leaving plot output in the repository:

```sh
MPLBACKEND=Agg uv run --locked python - <<'PY'
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import os
import runpy
import tempfile

examples = [Path('examples/wfq.py').resolve(),
            Path('examples/two_level_wfq.py').resolve()]
for example in examples:
    with tempfile.TemporaryDirectory(prefix='ns-wfq-example-') as workspace:
        os.chdir(workspace)
        with redirect_stdout(StringIO()):
            state = runpy.run_path(str(example))
        sink = state['ps']
        print(example.name, sum(sink.packets_received.values()),
              sum(sink.bytes_received.values()))
        schedulers = ([state['wfq_server']] if 'wfq_server' in state else
                      [state['drr_server'],
                       *state['drr_server_per_group'].values()])
        for server in schedulers:
            assert server.total_packets() == 0
            assert all(server.byte_size(c) == 0 for c in server.all_flows())
            assert not server.active_set
            assert server.packet_in_service() is None
            assert not server.upstream_stores
            assert not server.upstream_updates
            assert not server.store.items
PY
```

## Size and educational readability

Counts follow Phase 0's AST/tokenize categories: nonblank docstring and
comment-only lines are explanatory; remaining nonblank lines are code-bearing,
a proxy rather than an executable-statement count. Inline comments overlap
code-bearing lines and are counted separately.

| File | Physical before → after | Code-bearing before → after | Explanatory before → after | Blank before → after |
| --- | ---: | ---: | ---: | ---: |
| `ns/scheduler/wfq.py` | 262 → 283 (+21) | 148 → 154 (+6) | 68 → 90 (+22) | 46 → 39 (-7) |
| New `tests/scheduler/test_wfq.py` | 0 → 255 | 0 → 172 | 0 → 16 | 0 → 67 |

Production inline comments remain zero. The only new scheduling state is a
local wakeup event plus class activity counts separated from waiting telemetry.
A small local helper shares virtual-time advancement, and the service loop now
shares serialization and completion across ordinary and retained forwarding.
Comments explain model limits, units, class activity, first tags, selection
timing, tie ordering, retention, and callback timing. No execution engine,
scheduler framework, runtime module, or dependency was added.
