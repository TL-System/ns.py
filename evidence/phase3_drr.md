# Phase 3: Deficit Round Robin

Implemented against accepted Phase 2 `cf9488c` on 2026-10-03. The inspected Days
checkout is `9ff20eac16dcdf752510b05cbcf526684dc05146`. This task owns
`ns/scheduler/drr.py`, `tests/scheduler/test_drr.py`, the DRR cases in
`tests/scheduler/test_servers.py`, and the misleading opening explanation in
`examples/drr_jumbo.py`. The phase coordinator identifies the review candidate
and performs commits, integration, and publication.

## Algorithm and accounting

DRR keeps one FIFO and byte deficit per class. A new backlogged class joins the
tail of the active list. At each visit its configured quantum is added to its
deficit; consecutive FIFO heads may be selected while credit covers their sizes.
An unaffordable head is held separately so it cannot move behind later arrivals.
Residual credit carries to another visit only while the waiting queue stays
backlogged. Selecting the last waiting packet immediately resets credit and ends
that visit. A same-class arrival during its serialization starts a fresh visit
at the active-list tail. The current visit is tracked separately so arrivals to a
still-backlogged class cannot insert its next turn before other active classes.

Quanta remain fixed at `max(1500, mtu_bytes) * weight / min_weight` bytes. A
4500-byte packet with a 1500-byte quantum takes three visits, while another class
can send its 1500-byte heads between visits. With both classes initially queued,
the hand-derived departure order is small, small, jumbo, small; at 12000 bits/s,
the departure times are 1, 2, 5, and 6 seconds. A sole 9000-byte packet arriving
at 2 seconds accumulates six visits without a physical service gap and departs
at 8 seconds. We removed the old assertion that a packet must inflate every
class's quantum: that behavior changed the configured byte allocation and let
a jumbo jump ahead of eligible competing traffic. The legacy test now asserts
fixed quanta and the corresponding observable order.

Selection spends byte credit and removes waiting counts before serialization.
The packet in service is reported separately. `size`, `byte_size`, and
`total_packets` exclude local service and packets already handed to a downstream
zero-buffer scheduler, even when their store references remain retained. Class
IDs govern all accounting and debug output; multiple flow IDs mapped to one
class share FIFO order and credit. The previous debug path indexed deficits by
raw flow ID and raised `KeyError` for such mappings.

Service is nonpreemptive and lasts `8 * packet_bytes / rate_bps` seconds. A
zero-time yield before each visit lets already scheduled arrivals at that time
join selection, including a pending competing arrival while a jumbo accumulates
credit. It also keeps repeated logical-credit visits cooperative with SimPy.
This is a local boundary convention, not a replacement event engine or a promise
about arbitrarily deep same-time chains in user processes. Rates must be finite
and positive; weights and the configured MTU scale must be finite and positive,
with at least one configured class. Unknown classes are rejected before changing
accounting. Rate-zero scheduler service was not added.

The `put()`/`out` protocol, packet identity, list/dictionary weights, class mapping,
and zero-buffer hooks remain available. A test retains both packet references
through local completion, then pulls them and verifies one upstream callback per
packet and empty hook mappings. Direct injection in zero-buffer mode safely works
without optional upstream hooks. Cross-class removal from a shared upstream
store is also part of the phase's composed-scheduler audit; this task's retained
handoff test uses one class and does not establish arbitrary hierarchy ordering.

## Days comparison boundaries

Current CPU uses the shared scheduler transitions in `executor/src/scalar.rs`.
The relevant source is `DrrSchedulerState` in `executor/src/model.rs:47`, and
`scheduler_select_position` in `executor/src/scalar.rs:6443`. Days has fixed
byte quanta, byte deficits, FIFO heads within each class, and nonpreemptive
service-start selection. Its test
`drr_accumulates_exact_byte_quanta_across_wraps` exercises a packet larger than
its quantum; `drr_and_wrr_are_byte_identical_on_scalar_and_cpu` compares the
complete shared transition result for CPU workers 1, 2, and 4.

There are two explicit variant differences. Days scans numerical class IDs from
a persistent class cursor and adds all backlogged classes' quanta on cursor
wrap. Python preserves textbook active-list FIFO order and adds quantum at each
class visit. Thus activation order 2, 0, 1 departs in that order in the Python
test, whereas a fresh Days cursor selects class 0 first. Days also resets an
absent class's credit only on a wrap; it may retain residual credit after the
last packet is selected and after the scheduler becomes idle. Python discards
credit when the waiting class empties. A later arrival before Days's next wrap
can therefore see credit that Python intentionally discarded. These differences
are not floating-point tolerances and must remain visible in reference fixtures.

This task establishes independent orders/times and records source inspection;
it does not claim a new CPU execution from this task. The phase's scheduler
reference task records actual CPU fixtures for shared behavior and these
different decisions. Numeric comparisons must use integer-nanosecond intervals
or account for Days's per-serialization nanosecond ceiling. Python retains
floating-point seconds. Tests here drain with `env.run()` so an exclusive
numeric SimPy stop does not omit the final departure.

## Red/green validation

The first new suite, before changing production code, produced **16 failed,
4 passed**. It exposed jumbo inflation and the resulting selection order, stale
credit across empty-at-selection service, premature reinsertion of the current
visit, mapped-class debug failure, service counted as waiting, and invalid
configuration handling. A later test for an already scheduled time-zero arrival
failed against the initial repair, then passed after the visit-boundary yield.

The final independent suite was also run against the accepted baseline module,
without changing working-tree files. It produced **23 failed, 4 passed**. The
baseline-module command is reproducible from the accepted revision:

```sh
uv run --locked python - <<'PY'
import subprocess
import sys
import types
import pytest

baseline = subprocess.check_output(
    ['git', 'show', 'cf9488c:ns/scheduler/drr.py'], text=True
)
module = types.ModuleType('ns.scheduler.drr')
exec(compile(baseline, 'cf9488c/ns/scheduler/drr.py', 'exec'), module.__dict__)
sys.modules[module.__name__] = module
raise SystemExit(pytest.main(['-q', '--tb=no', 'tests/scheduler/test_drr.py']))
PY
```

| Exact command | Observation |
| --- | --- |
| `uv run --locked pytest -q tests/scheduler/test_drr.py tests/scheduler/test_servers.py -k drr` | 32 passed, 8 deselected in 0.03 s. |
| `uv run --locked python examples/two_level_drr.py` | Exit 0; six flows each delivered three packets. |
| `git diff --check` | Passed. |

The finite example ran with its checked-in settings and stop of 100 seconds.
The coordinator runs the final whole-tree regression gate after the other
scheduler tasks are integrated.

## Source growth

Production counts compare only `ns/scheduler/drr.py` with `cf9488c` using Phase
0's AST/token categories: explanatory lines are nonblank docstrings and
comment-only lines; code-bearing lines are all other nonblank lines, including
delimiters. The added current-visit field repairs activation timing without
introducing a scheduling framework.

| Category | Before | After | Change |
| --- | ---: | ---: | ---: |
| Physical | 321 | 341 | +20 |
| Code-bearing | 192 | 202 | +10 |
| Explanatory | 70 | 83 | +13 |
| Blank | 59 | 56 | -3 |
| Inline comments (overlap code-bearing) | 0 | 0 | 0 |
