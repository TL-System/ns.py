# Phase 3 scheduler composition and switch wiring

Task baseline: `02f48ae` (SP, Virtual Clock, DRR and its valid-None-class repair,
and scheduler CPU reference fixtures already integrated). Scope is scheduler
`update(packet)` callbacks, exact retained-store removal, class-mapped monitor
service inclusion, and scheduler/switch composition tests. Scheduler algorithms
remain owned by their individual tasks. WFQ's algorithm decision and independent
red tests are pending; the passing WFQ plumbing observations below do not certify
its finish-tag model or waiting/service telemetry.

## Ownership repair

Zero-buffer composition separates a local selection queue from the store retaining
upstream ownership. A downstream scheduler may map classes differently and serve
the retained packets in a different order. Calling an unconditional upstream
`get()` removes the FIFO head or smallest heap tag, which can be a different
packet from the one whose callback releases accounting. Eventual byte totals can
still reach zero while ownership is wrong at every intermediate handoff.

All four scheduler callbacks now release the selected packet by object identity.
A tiny `ns/utils/retained_store.py` helper shares the two store cases. For a plain
SimPy store, it moves that packet to the front without changing the relative order
of other objects and calls the real `Store.get()`. For a `TaggedStore`, the optional
`get(packet)` selects that identity, restores the heap, and succeeds the usual
SimPy get event. Remaining tags and insertion counters are preserved. Both paths
therefore retain pending-put wakeups; raw list removal alone would miss them.
This narrow helper assumes a retained ownership store, whose local selection uses
a separate queue rather than a pending get on the retained store. Existing minimal
adapters exposing only `get()` keep that callback convention.

`TaggedStore.get()` retains its previous lowest-tag ordering and equal-tag FIFO
ties. An identity get that cannot yet find its object waits without reserving
unrelated objects or blocking later gets for those objects. The new optional
argument treats `None` as the existing ordinary-get request; scheduler payloads
are packet objects. No execution engine or scheduler framework was added.

Hooks are popped before invoking the callback, so synchronous reentry cannot
release another packet or invoke another callback. Repeated releases are harmless.
WFQ now also accepts direct zero-buffer input without an upstream hook, matching
the other three schedulers.

## Monitor and switch inspection

`ServerMonitor` maps the current packet through `server.flow_classes` before
adding service to a class's waiting counters. This avoids omitting service when
a string class ID differs from the packet's flow ID. Servers without a classifier
retain flow-ID compatibility, covered by the existing scripted-server monitor
tests. The process samples after each configured interval and reads the current
packet once per sample. SP, DRR, and Virtual Clock mapped-class tests observe one
100-byte packet in service plus one 40-byte packet waiting: queue-only samples
are 1 packet/40 bytes, inclusive samples 2 packets/140 bytes, and drained samples
are zero. WFQ's independent task still owns its waiting-counter correction.

`SimplePacketSwitch` and `FairPacketSwitch` required no runtime changes. Tests
verify all four supported scheduler names select the expected type, unknown names
raise, and forwarding uses the configured output index. Fair-switch egress ports
retain admission occupancy until the scheduler releases the original packet,
including its service time. With a two-packet limit, the first 100-byte and second
40-byte packets occupy 140 bytes and a third arrival drops; releases occur at
1 and 1.4 seconds at 800 bits/s. Another egress port independently transmits
50 bytes at 0.5 seconds. FIFO-switch routing and its capacity are also checked.

## Independent composition observations

The hierarchy test covers all **16 upstream/downstream scheduler pairs**. The
upstream merges three flows into one `group` class. The downstream maps them to
`blocker`, `low`, and `high`. A 100-byte blocker starts first; while it serializes,
a 2000-byte low packet and a 100-byte high packet arrive. SP's higher priority,
DRR's fixed 1500-byte quantum, and the heap schedulers' configured tags each
select high before low. The upstream runs at 800000 bits/s and the downstream
at 800 bits/s, so departures are independently calculated as **1.001, 2.001,
22.001 seconds**. Serialization uses `8 * bytes / bits_per_second`.

At those handoffs both the root FIFO and the upstream scheduler must retain,
respectively, `{low, high}`, `{low}`, and nothing. Root retained bytes are
2100, 2000, and zero. Each callback and delivery receives the original object
exactly once, and all hook maps and physical ownership stores drain. A fourth
arrival while all three admitted packets remain downstream is dropped despite
the upstream having finished all local service. The test asserts intermediate
identity and occupancy rather than accepting only a final aggregate total.

Eight additional release cases cover each scheduler against a capacity-three
FIFO and tagged store. A fourth put starts blocked, then wakes after exact
release. All four objects deliberately share a packet ID and class but have
distinct identities. Remaining FIFO order and equal-tag admission order survive,
and a newly admitted lower-tag packet still wins the tagged store's next get.

## Red and green checks

The first 33 tests ran before production edits: **25 failed, 8 passed**. The final
38-test file replayed against all pre-composition production modules at `02f48ae`:
**27 failed, 11 passed**. That replay changes only modules in the Python process,
leaving the worktree untouched:

```sh
uv run --locked python - <<'PY'
import subprocess
import pytest
import ns.scheduler.drr as drr
import ns.scheduler.monitor as monitor
import ns.scheduler.sp as sp
import ns.scheduler.virtual_clock as vc
import ns.scheduler.wfq as wfq
import ns.utils.taggedstore as tagged

for module in [tagged, sp, drr, wfq, vc, monitor]:
    path = module.__file__.split('ns.py/', 1)[1]
    baseline = subprocess.check_output(['git', 'show', f'02f48ae:{path}'])
    exec(compile(baseline, '<pre-composition ' + module.__name__ + '>', 'exec'),
         module.__dict__)
raise SystemExit(pytest.main([
    '-q', '--tb=no', 'tests/scheduler/test_composition.py'
]))
PY
```

A separate strengthened asynchronous targeted-get test first failed because an
absent requested identity blocked an ordinary get for an unrelated object. The
targeted branch now continues scanning pending gets, and that reproducer passes.

Final checks:

- `uv run --locked pytest -q tests/scheduler/test_composition.py tests/utils/test_taggedstore.py tests/scheduler/test_servers.py`:
  **58 passed** (0.04 seconds).
- `uv run --locked pytest -q --ignore=tests/scheduler/test_wfq.py`:
  **216 passed** (0.17 seconds). The pending WFQ algorithm tests are explicitly
  excluded; this is the composition regression check, not the Phase 3 gate.
- `git diff --check`: passed.
- Existing two-level SP, DRR, and WFQ examples: each delivers **18 packets**, with
  all scheduler hooks and retained stores empty. The scenarios already finish
  their sources at 3 seconds and run to 100 seconds. Exact replay and assertions:

```sh
MPLBACKEND=Agg uv run --locked python - <<'PY'
import contextlib
import io
from pathlib import Path
import runpy

for filename in ['two_level_sp.py', 'two_level_drr.py', 'two_level_wfq.py']:
    with contextlib.redirect_stdout(io.StringIO()):
        values = runpy.run_path(str(Path('examples', filename).resolve()))
    assert sum(values['ps'].packets_received.values()) == 18
    scheduler = values['drr_server']
    assert not scheduler.upstream_stores
    assert not scheduler.upstream_updates
    for leaf in values['drr_server_per_group'].values():
        assert not leaf.upstream_stores
        assert not leaf.upstream_updates
        if hasattr(leaf, 'store'):
            assert not leaf.store.items
        else:
            assert all(not store.items for store in leaf.stores.values())
    print(filename, '18 delivered; hooks and retained stores empty')
PY
```

## Size and readability

Counts follow Phase 0's AST/tokenize physical-line categories. Explanatory lines
are nonblank docstrings/comment-only lines; code-bearing lines are a source-size
proxy including declarations and delimiters, not executable statement counts.

| File | Physical before → after | Code-bearing before → after | Explanatory before → after | Blank before → after |
| --- | ---: | ---: | ---: | ---: |
| `ns/scheduler/sp.py` | 249 → 243 (-6) | 138 → 136 (-2) | 74 → 70 (-4) | 37 → 37 |
| `ns/scheduler/drr.py` | 343 → 343 | 203 → 204 (+1) | 84 → 83 (-1) | 56 → 56 |
| `ns/scheduler/wfq.py` | 262 → 262 | 147 → 148 (+1) | 69 → 68 (-1) | 46 → 46 |
| `ns/scheduler/virtual_clock.py` | 242 → 242 | 125 → 126 (+1) | 80 → 79 (-1) | 37 → 37 |
| `ns/scheduler/monitor.py` | 70 → 77 (+7) | 23 → 30 (+7) | 31 → 29 (-2) | 16 → 18 (+2) |
| `ns/utils/taggedstore.py` | 78 → 97 (+19) | 31 → 42 (+11) | 27 → 34 (+7) | 20 → 21 (+1) |
| `ns/utils/retained_store.py` | 0 → 21 | 0 → 8 | 0 → 9 | 0 → 4 |
| New composition tests | 0 → 277 | 0 → 232 | 0 → 10 | 0 → 35 |

Production growth is **+27 code-bearing lines, +7 explanatory lines, +7 blank
lines** (+41 physical). Existing inline comment count remains three in the tagged
store. The helper explains ownership versus selection, exact identity, FIFO order,
and event wakeups. Heap comments explain why arbitrary removal needs heap repair
and why an absent identity must not reserve other packets. Monitor documentation
uses the same class IDs as scheduler telemetry and explains service inclusion.
