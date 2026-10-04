# Phase 6 routing, topology, configuration, and measurement audit

Accepted input: ns.py Phase 5 `65dfd2d`, branch
`modernize-python314-correctness`. Read-only reference: Days
`9ff20eac16dcdf752510b05cbcf526684dc05146` at
`/Users/bli/Playground/days`. This task follows
[the requested harness](https://baochun.org/2026-09-05/) and the user's internal
agent override. No reference checkout, proxy, traffic-source, shaper, transport,
or scheduler implementation was edited by this task.

## Observable corrections

- `FlowDemux` uses nonnegative integer flow IDs as output indexes. Negative IDs
  previously selected a Python list entry from the end; strings and `None`
  raised exceptions. Unknown IDs and disconnected outputs now use the supplied
  default, or count one local drop when no default exists.
- `FIBDemux` retains terminal-delivery precedence, supports integer or string
  flow keys, preserves caller-owned empty endpoint dictionaries, and handles
  missing/invalid/disconnected output routes in the same way. Route selection is
  separate from downstream `put()`: downstream exceptions propagate instead of
  causing a second delivery through the default. Unconfigured switches therefore
  drop and account for unroutable packets rather than indexing `None`.
- Both demux counters distinguish local routing failure from a downstream
  port's capacity drop. `packets_received` counts each arrival; local
  `packets_dropped` increases only when no connected route/default exists.
- `RandomDemux` snapshots the supplied relative weights, requires a nonempty
  list of finite nonnegative weights with a finite positive total, and preserves
  `random.choices` semantics: weights need not sum to one. A selected disconnected
  branch counts a drop; it does not redraw and bias the configured distribution.
- Splitters prepare every branch before any downstream call. Distinct packet
  objects preserve the logical ID and own independent `prio` and `perhop_time`
  dictionaries, including nested metadata. The first branch retains the original
  object. Opaque application payload remains shared; no payload serialization or
  deep copying is introduced. An unused N-way branch can stay disconnected.
- `Config` publishes its singleton only after successful loading/conversion, so
  a failed load can be retried. YAML is read inside a context manager using
  `safe_load`. Empty documents and missing `params` use an empty parameter
  mapping. Nonmapping roots or explicit nonmapping `params` raise a local
  `ValueError`. Valid keys remain sorted namedtuple fields; invalid or mixed-type
  keys preserve the original mapping and recursively converted values. The
  existing environment override (`config_file`), CLI options, and successful
  singleton lifecycle remain intact. Namedtuple conversion is attempted only
  when every key is a string, because Python otherwise stringifies numeric
  infinity/NaN keys into apparently valid attribute names.
- `generate_fib(tcp=True)` keeps the existing ACK ID rule, `data ID + 10000`,
  and rejects actual data/ACK ID collisions before mutating the graph. Previously
  flows 0 and 10000 could silently overwrite each other's forwarding entries.
  No ID allocator or routing framework was added.
- Recurring monitor intervals must be positive and finite, in simulation
  seconds. Zero intervals previously produced an unbounded series of samples at
  one instant; NaN/infinite intervals could leave time or sampling unusable.
  Rejection happens when the process requests the interval, before scheduling
  its timeout. Ordinary samples still wait one interval before observing state.

## Measurement definitions and already-correct behavior

Port admission includes waiting work, local service, and packets retained for a
zero-buffer downstream element. `PortMonitor` uses accepted arrivals minus
releases, rather than physical store length, to cover the pending `Store.get()`
handoff. With service excluded it subtracts only the local busy packet and its
bytes. Retention remains included until the downstream release callback.

`ServerMonitor` reports scheduler waiting work by mapped class, optionally adding
the current local service packet once to that class. It excludes packets whose
local service finished but whose physical store objects remain retained
downstream. Phase 3 established these definitions correctly; this task changes
only interval validation. Tests sample away from simultaneous service completion
boundaries and cover SP, DRR, WFQ, and Virtual Clock under different upper/lower
class maps. At .006/.012/.018 seconds, an upper 80000-bit/s scheduler processing
100-byte then 40-byte packets reports waiting counts 1/0/0 and inclusive counts
2/1/0. Its 800-bit/s downstream still retains both packets at .018 seconds. The
upstream port retains 140 bytes until the downstream releases the exact objects.

`SimplePacketSwitch` and `FairPacketSwitch` already compose the correct FIFO or
selected scheduler with bounded egress ports. The latter retains shared-buffer
capacity until downstream release and maps scheduler classes without changing
routing flow IDs. Existing Phase 3 composition tests cover all four schedulers,
capacity, ordering, non-preemption, and object release. No switch implementation
change is necessary; corrected FIB lookup supplies its routing behavior.

`PacketSink` already maintains per-flow or per-source counts/bytes and first/last
arrivals regardless of sample flags; its count-based first-arrival rule handles
t=0 and its per-hop snapshots prevent later path metadata changes from rewriting
observations. Existing Phase 2 sink tests close this Phase 6 inspection. No sink
edit is necessary.

## Topology and Days reference boundaries

The FatTree builder already uses integer halves, rejects nonpositive/odd/nonint
`k`, and builds the expected structure. Tests independently count k=2 as 1 core,
2 aggregation, 2 edge, 2 hosts, and 6 links; k=4 as 4/8/8/16 nodes in these layers
and 48 links. Switches have degree k, hosts degree 1; all host pairs have symmetric
distances of 2, 4, or 6 hops according to rack/pod membership. The docstring's
stale `tier` and edge-type names were corrected to match existing attributes.

Forwarding tests wire actual FIFO switches with generated FIBs for explicit
cross-pod paths in both topologies. At 800 bits/s, a 100-byte packet traverses
six independent egress links and arrives at t=6 seconds; its 40-byte reverse ACK
arrives at t=2.4 seconds. They preserve identity and delivered byte counts, each
hop matches a real edge, reverse next hops retrace the forward route, and every
local routing drop count is zero. Flow generation tests inject endpoint/path
selection, so they assert an explicit shortest path rather than equating seeds.
GraphML roundtripping exercises the installed NetworkX API. Unsupported file
suffixes retain the existing print-and-return behavior; this audit introduces no
new file-format policy.

Read-only reference inspection covered Days `src/topos/build.rs` (FatTree
parameter validation, edge/aggregation/core construction, and host attachments),
`src/topos/config.rs` (typed topology/switch configuration), and
`src/topos/route.rs` (deterministic shortest paths and configured/ECMP routes).
Days represents hosts separately from its switch graph and defaults to one host
per edge; ns.py includes k/2 hosts per edge as explicit leaf nodes. Node numbers
are consequently not comparable without an explicit topology mapping. ns.py's
random choice among equal-cost shortest paths also differs from current Days'
deterministic shortest-path tie selection. Tests establish valid shortest routes
and exact reverse forwarding, without claiming identical tie choices.

Current CPU imports and runs the transition state from `executor/src/scalar.rs`.
Its `packet_remote_target_for` walks the declared forward/reverse link route and
reports `FlowRouteMiss` on a missing step; its arrival observations record
admitted/dropped/delivered disposition. Those shared routing/conservation ideas
inform inspection here. Python's default/drop demux behavior is a public
component policy, not an assertion that Days uses the same fallback behavior.
No new CPU equivalence fixture is claimed. Current CPU has no direct random
demux, packet-copy splitter, YAML singleton parser, periodic monitor, or matching
statistics-collector API. Their independent tests close these explicit gaps;
legacy implementations are not used as current-CPU evidence.

## Inventory closure and validation

| Owned inventory row | Closure |
| --- | --- |
| `demux/fib_demux.py`, `flow_demux.py`, `random_demux.py` | Corrected local route/drop rules; `tests/demux/test_demux.py` |
| `utils/splitter.py` | Branch snapshots and independent metadata; `tests/utils/test_splitter.py` |
| `utils/config.py` | Retryable loading, defaults, YAML data types; `tests/utils/test_config.py` |
| `topos/fattree.py`, `topos/utils.py` | Structure/routing inspection, ACK collision correction; `tests/topos/test_routing.py` |
| `port/monitor.py` | Phase 2 occupancy inspected/preserved; `tests/port/test_port.py`, `test_port_monitor.py` |
| `scheduler/monitor.py` | Phase 3 class/service/retention inspected/preserved; `tests/scheduler/test_server_monitor.py`, existing monitor/composition tests |
| `switch/switch.py` | Inspected, unchanged; `tests/scheduler/test_composition.py` and actual FatTree forwarding |
| `packet/sink.py` (Phase 6 accounting inspection) | Inspected, unchanged; `tests/packet/test_sink.py` and branch/link tests |

The initial focused 66-test suite, run before production edits against accepted
Phase 5 behavior, produced **51 failures and 15 passes**. This count includes
new accounting assertions and diagnostic improvements; it is not 51 distinct
algorithm faults. The later ACK collision reproducer separately failed with
`DID NOT RAISE ValueError` before its production fix.

Commands and observations:

```sh
uv run --locked pytest -q tests/demux tests/utils/test_splitter.py tests/utils/test_config.py tests/topos tests/port/test_port_monitor.py tests/scheduler/test_server_monitor.py
# 67 passed before review fix; the two new YAML cases bring this suite to 69

uv run --locked pytest -q tests/demux tests/utils/test_splitter.py tests/utils/test_config.py tests/topos tests/port/test_port.py tests/port/test_port_monitor.py tests/packet/test_sink.py tests/scheduler/test_server_monitor.py tests/scheduler/test_composition.py tests/scheduler/test_servers.py tests/scheduler/test_sp.py tests/scheduler/test_virtual_clock.py
# 174 passed after the YAML key review fix (172 before it)

MPLBACKEND=Agg uv run --locked python examples/fattree.py
# Exit 0
```

Pytest emitted eight warnings while trying to clean unrelated, pre-existing
temporary test directories. They do not concern simulator results, and this
task did not remove those resources. Task-owned diffs pass `git diff --check`.
Full phase validation
and exact candidate-commit review remain the orchestrator's integration gate.

Fresh review of candidate `6b5245b` found that sorting/constructing namedtuple
fields alone does not reject every numeric YAML key: `.inf` and `.nan` are loaded
as floats, then coerced by namedtuple to valid-looking `inf` and `nan` fields.
Two actual YAML load tests reproduced this loss of key type before the fix
(both failed with a namedtuple where a mapping was required). An explicit
all-string-key check now retains these mappings while still recursively
converting their nested values. The NaN test looks up the retained key object
instead of relying on NaN equality. All eleven configuration tests and all 174
relevant regression tests pass after the correction. No other reviewed behavior
changed.

## Size and readability

Counts use AST docstring ranges and comment-only physical lines as explanatory;
other nonblank lines are code-bearing, including delimiter lines. Inline comments
remain code-bearing. This is a readable source-size proxy, not an executable
statement count. Across the eleven audited production modules, accepted Phase 5
has 786 physical / 431 code-bearing / 230 explanatory / 125 blank lines; the
candidate has 864 / 482 / 256 / 126. Net growth is **78 physical, 51 code-bearing,
26 explanatory, and 1 blank line**. The unchanged switch/sink modules contribute
no growth; FatTree's documentation correction removes two explanatory lines.
The six new test files total 487 physical / 393 code-bearing / 17 explanatory /
77 blank lines.

The changes add no routing/configuration framework or replacement execution
engine. They retain direct `put()`/`out` composition and small SimPy monitor
loops. New comments explain negative list indexes, exactly-once fallback,
snapshot-before-forwarding, ACK identity collisions, retryable singleton
publication, and why recurring sampling must advance simulated time.
