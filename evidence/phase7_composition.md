# Phase 7 composition task

Implemented against accepted Phase 6 `aa73e177b0b5215485af73ed3f2d14e6d4a73997`.
These are integrations of already-correct components; no runtime behavior was
changed, so there is no artificial red/green repair claim.

## Independent network invariants

`tests/integration/test_composed_networks.py` adds two finite cases:

- A byte-limited shared Port feeds one aggregate DRR class, then a different
  three-class SP map, a token bucket, and a propagation wire. Sizes are 100,
  200, 40, and 60 bytes. The first packet starts before the higher-priority
  arrivals, so nonpreemptive SP emits the original objects in order 0/2/3/1.
  Link serialization is independently calculated as `8 * bytes / bits_per_s`.
  SP completes at 1.001/1.401/2.001/4.001 seconds; 50 byte tokens per second
  and a 200-byte bucket defer the last packet until 5.001. Wire arrivals add
  exactly .1 seconds. Release callbacks remove each selected original object
  and leave precisely the expected other objects and resident byte counts.
  At .25 seconds DRR reports no local work while the Port still holds all
  400 bytes. At 4.25 seconds both schedulers report no local work while 200
  bytes remain resident for the shaper. A one-byte excess admission drops.
  Final port/scheduler/shaper/wire stores, hooks, service, and telemetry drain.
- A 1001-byte Reno transfer uses a 300-byte MSS, 1200-byte initial window,
  150-byte/s token refill, a full 1001-byte bucket, a 24000-bit/s bottleneck
  with 600 resident bytes, and two .01-second wires. The initial burst admits
  two segments and drops the third segment plus the 101-byte tail. The first
  retry starts at 1.22 seconds and waits .78 seconds for tokens. Its ACK at
  2.12 restarts the backed-off timer; the tail retries at 4.12. All retries
  occur after the .5-second new-data deadline. Exact attempts, object identity,
  serialization/propagation times, and ACK prefix 300/600/900/1001 are checked.
  The conservation oracle is 1402 attempted bytes minus 401 dropped bytes =
  1001 physical received and unique application bytes. Transport state, queues,
  monitors, and timers drain, and observation through 10 seconds shows no stale
  retransmissions.

Existing coverage supplies the broader combinations without duplicating cases:
`tests/scheduler/test_composition.py` checks all 16 ordered SP/DRR/WFQ/Virtual
Clock pairings, differing classifiers, retained identity, admission, and monitor
semantics. `tests/topos/test_routing.py` checks small k=2 and k=4 FatTrees,
six-hop cross-pod data/ACK forwarding through actual switch ports and generated
FIBs, independent 6-second/2.4-second timing and byte totals, and route collision
rejection. These supplement the new congestion and mixed-size hierarchy cases;
they do not claim a new Days CPU comparison. Accepted CPU FIFO, scheduler, and
TCP comparisons remain in the Phase 2/3/5 fixtures and evidence.

## Educational example and simplicity

`examples/composed_network.py` reproduces the lossy Reno composition with direct
`out` assignments and two bounded observations. It explains bit/byte units,
resident capacity, token waiting, and recovery after the new-data deadline.
It prints `2 drops; 600 of 1001 application bytes delivered`, then confirms all
1001 bytes are delivered and acknowledged, with peak occupancy 600 and an empty
final queue. It needs no random seed, plotting backend, sockets, or arguments.
The curated smoke runner now includes it under the existing 90-second timeout.

Production executable and explanatory line growth are both **zero**. The only
test helper is a small passive capture that preserves object identity and
forwards ordinary `put()` arguments. No fixture-generation or network framework
was introduced. Integration comments explain observable timing and ownership;
the two tests deliberately retain their explicit setups and expected values.

## Validation

- `uv run --locked pytest -q tests/integration/test_composed_networks.py`: 2 passed.
- `uv run --locked pytest -q tests/integration/test_composed_networks.py tests/scheduler/test_composition.py tests/shaper/test_token_buckets.py tests/packet/test_tcp_transport_integration.py tests/flow/test_tcp_integration.py tests/topos/test_routing.py`: 101 passed.
- `uv run --locked python examples/composed_network.py`: expected statistics above.
- `uv run --locked python scripts/smoke_examples.py`: basic, TCP, FatTree, and
  composed-network examples passed.
- `git diff --check`: passed.

The focused run reported the eight already-recorded pytest cleanup warnings
from unrelated read-only temporary model directories; those directories were
preserved. Full-suite, reference, package, and final readability gates belong
to Phase 7 integration and are not claimed by this task record.
