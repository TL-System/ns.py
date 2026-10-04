# Phase 3 strict-priority scheduler

Task baseline: accepted Phase 2 `cf9488c72d95cf5ea2dacebeabe9853864b5a1eb`.
Scope: `ns/scheduler/sp.py` and `tests/scheduler/test_sp.py`. Existing SP tests
and the constructor, `put()`/`out`, priority lists/dictionaries, and upstream
callback conventions are preserved.

## Decisions and corrections

Larger priority numbers win. Classes with equal priority share one FIFO, which
also preserves order between different flow IDs mapped to the same class.
Service is nonpreemptive: a high-priority arrival cannot interrupt the current
packet; every subsequent service start scans priorities again. At 800 bits/s,
100 bytes require one second, 40 bytes require 0.4 seconds, and 10 bytes require
0.1 seconds. The mixed-priority test therefore expects the first low-priority
packet at 1 second, the later high-priority packet at 1.1 seconds, and the waiting
low-priority packet at 1.5 seconds.

The original scheduler selected its next packet immediately on a completion
timeout, ahead of an arrival at exactly the same time if that arrival's timeout
was inserted later. One zero-time wait before each selection lets already
scheduled same-time arrivals become eligible. The boundary test inserts the
high-priority arrival timeout during service and expects identities
`first, high, low` at seconds `1, 2, 3`; the original produced
`first, low, high`. This local wait is not a global phase engine and does not
promise Days ordering for arbitrary chains of zero-time user processes.

Queue telemetry now consistently uses the mapped class ID rather than looking
up a priority bucket with that ID. Waiting packet/byte counters exclude the
packet in service, so `ServerMonitor` may add service exactly once. They also
exclude packets whose local serialization completed but whose ownership remains
in `stores` for downstream backpressure. The physical ownership stores remain
independent. Two classes sharing one priority, and two flows sharing one class,
have independent and hand-counted measurements. `total_packets()` reports
waiting work, and the wakeup store retains at most one idle notification even
when each service interval receives a new packet.

Upstream release now removes the selected packet identity from a shared plain
SimPy FIFO, preserving the order of all other resident packets and using
`Store.get()` to preserve pending-put wakeups. This corrects the original
unconditional head removal when SP chooses a higher-priority packet behind a
lower-priority packet. Callback maps are removed before invoking the callback.
Standalone input with `zero_buffer=True` works without upstream hooks.
`zero_downstream_buffer=True` delays upstream release until the downstream
pull, as before. Minimal store adapters exposing only `get()` retain that API;
shared tagged-store composition is audited by the separate composition task.

Finally, `current_packet` is cleared before synchronous downstream callbacks,
so an observer sees completion and may inject another packet safely.
Positive scheduler rates remain the documented convention.

## Reference inspection

Days revision: `9ff20eac16dcdf752510b05cbcf526684dc05146` at
`/Users/bli/Playground/days`.

- `executor/src/model.rs`: `SchedulerKind::StaticPriority` stores the class
  priorities.
- `executor/src/scalar.rs`: `switch_sp_insertion_position` inserts ahead of the
  first queued packet with a strictly smaller priority; equal priorities remain
  in arrival order. `queue_serves_head` and `switch_tx_ready` select the ordered
  head only when a link is ready, maintaining nonpreemption.

This is source inspection, not an actual CPU equivalence result. Actual Days CPU
SP fixtures are required and implemented in the separate Phase 3 reference task.
Class mapping must be aligned there: ns.py permits arbitrary mapping functions
and dictionary keys, while Days derives scheduler classes from its flow records.

## Red/green validation

Before the repair, the initial new suite produced 8 failed / 4 passed. The final
13-test suite was also executed against the accepted-baseline SP class loaded in
memory from `git show` (without changing the working tree): 8 failed / 5 passed.
Failures assert next-packet identity, queue measurements, release identity,
missing-hook safety, and synchronous service visibility rather than copying
implementation state transitions.

After the repair:

- `uv run --locked pytest -q tests/scheduler/test_sp.py`: 13 passed.
- `uv run --locked pytest -q tests/scheduler/test_sp.py tests/scheduler/test_servers.py -k 'sp or monitor'`:
  17 passed / 9 deselected; no existing SP or monitor test was weakened.
- `uv run --locked python examples/two_level_sp.py`: passed; all six flows
  delivered three packets, with zero-buffer releases continuing through both
  scheduler levels.

## Source size and readability

The Phase 0 AST/tokenize physical-line definition separates nonblank docstrings
and comment-only lines from code-bearing lines (a proxy, not statement counts).

| SP production | Before | After | Growth |
| --- | ---: | ---: | ---: |
| Physical | 241 | 249 | +8 |
| Code-bearing | 138 | 138 | 0 |
| Explanatory | 62 | 74 | +12 |
| Blank | 41 | 37 | -4 |

Inline comments remain zero. The new test file has 252 physical lines: 197
code-bearing, four explanatory, and 51 blank. The process remains a short
priority scan plus one packet serialization; removing duplicate forwarding
branches pays for the class counters and ownership correction. Comments explain
timing, units, telemetry, tie order, and callback ownership without a new
framework or dependency.
