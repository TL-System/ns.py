# Phase 5: BBR controller and delivery sampler

Accepted Phase 4 revision: `18c6de4`. Days reference remains
`9ff20eac16dcdf752510b05cbcf526684dc05146`. Current Days CPU has no BBR model;
this task makes no CPU BBR equivalence claim and does not execute legacy Days.

## Model and scope

[The BBR model document](../docs/bbr.md) replaces the false Linux BBRv3 / RFC 8899
attribution with an explicit educational core BBR model. Its primary references
are pinned Linux v6.12 `tcp_bbr.c` and `tcp_rate.c`, the delivery-rate draft 02,
and BBR congestion-control draft 02. The latter describes BBRv2; neither its
richer loss bounds nor production v3 mechanisms are claimed implemented.
RFC 8899 concerns Datagram Packetization Layer Path MTU Discovery.

The controller retains recognizable Startup, Drain, ProbeBW and ProbeRTT modes
and the existing four named probing phases as a documented teaching cycle. Ten
packet-timed rounds replace an ACK-counted rate filter. Full-pipe detection runs
once per valid unrestricted round; application-limited observations cannot
prematurely end Startup. ProbeRTT holds for 200 ms after flight drains plus a
packet-timed round, refreshes expiry on exit, and restores saved cwnd. DOWN waits
for actual drain; loss can end UP before another round. Loss hooks conserve the
actual outstanding flight until the entry frontier is covered rather than
exiting merely because flight is less than cwnd. There is no durable v3 loss cap.

The sampler resets every valid ACK group, uses None for absent/consumed clocks,
rejects zero/too-short intervals without preserving an old rate, credits exact
newly covered ranges, and records newly declared losses. Snapshot choice uses
prior delivery and latest attempt time. Retransmissions refresh rate snapshots;
`Packet.time` still preserves original first-transmission latency. Window-limited
and unlimited bulk sources are not mistaken for lack of application supply.

Changes in the sender are limited to snapshot/group integration and correct
application-limit classification. Phase 4 MSS/tail/deadline rules, one oldest
range timer, synchronous send ownership, Karn RTT eligibility, and deferred
partial-recovery retransmissions are preserved. The existing two-argument
controller ACK callback remains compatible; `rs.rtt=-1` distinguishes absence of
an eligible sample from valid zero RTT. Obsolete sampler scratch fields were
removed after searching all in-tree users; the public sampling method names and
connection counters used by transport remain.

## Red and green observations

The first targeted additions, before changing production, produced **13 failed,
7 passed**. The final independent controller/sampler/integration tests can replay
against accepted Phase 4 source without changing the worktree:

```sh
uv run --locked python - <<'PY'
import importlib
import subprocess
import pytest
for name in ('ns.packet.rate_sample', 'ns.flow.bbr',
             'ns.packet.bbr_generator'):
    module = importlib.import_module(name)
    path = name.replace('.', '/') + '.py'
    source = subprocess.check_output(
        ['git', 'show', f'18c6de4:{path}'], text=True,
    )
    exec(compile(source, f'18c6de4/{path}', 'exec'), module.__dict__)
raise SystemExit(pytest.main([
    '-q', '--tb=no', 'tests/packet/test_rate_sample.py',
    'tests/flow/test_bbrv3.py', 'tests/flow/test_bbrv3_integration.py',
]))
PY
```

Observed: **20 failed, 10 passed**. Failures include division by a zero interval,
stale ACK group rates, retransmission attempt clocks, ACK-density-dependent
filter/startup, app-limited reductions and Startup termination, probe hold/expiry,
recovery exit, invalid-rate learning, actual DOWN drain, UP loss response,
absence-versus-zero RTT, sparse-write classification, recovery snapshots, and
synchronous delivery without an invented rate.

```sh
uv run --locked pytest -q tests/packet/test_rate_sample.py \
  tests/flow/test_bbrv3.py tests/flow/test_bbrv3_integration.py \
  tests/packet/test_bbr_generator.py tests/packet/test_bbr_transport.py
uv run --locked pytest -q
git diff --check
```

Observed candidate: **75 focused tests passed**; shared-tree full regression:
**409 passed**; diff whitespace check passed. The phase integrator records the
final merged example/build checks separately.

Observations establish bytes, clocks, and state decisions rather than merely
asserting positive progress. A 409600-byte flow over a 100000-byte/s port drains
exactly once, estimates that bandwidth, fills the pipe, and ends in ProbeBW.
The first two physical sends follow initial `512 / (2.885 * 8192 / 0.02)` pacing.
Five 100-byte writes at 0.2-second intervals remain application-limited, deliver
500 unique bytes, estimate 10000 bytes/s from the 10 ms round trip, and do not
falsely fill the pipe. Losing the first 100-byte segment causes exactly one fast
retransmission before the one-second RTO, retains original latency time zero,
uses its actual retransmit time for sampling, delivers all 700 bytes, reports
100 declared lost bytes, exits conservation, and leaves no timer. A direct
synchronous receiver delivers 700 bytes, valid RTT zero, bandwidth zero, and no
timer. Component tests separately exercise compressed ACK bounds, ten-round
filter expiry, many ACKs in one round, application-limit frontier equality, and
ProbeRTT's hold beginning only after drain.

The Phase 4 test asserting unchanged retransmission sampling elapsed clocks was
updated: with original send at second 1 and retry at second 5, send elapsed is
now four seconds while ACK elapsed remains four seconds. Original emitted
metadata and first-transmission latency remain unchanged; ambiguous recovery
still does not teach the RTO. This is a deliberate rate-estimator correction.

## Source counts and readability

Counts use the Phase 0 categories: nonblank docstrings/comment-only lines are
explanatory; other nonblank lines are code-bearing, including delimiters. Inline
comments overlap code-bearing counts. These counts do not measure complexity.

| Owned production | Accepted physical/code/explanatory/blank | Candidate physical/code/explanatory/blank |
| --- | --- | --- |
| `ns/flow/bbr.py` | 313 / 237 / 28 / 48 | 275 / 213 / 31 / 31 |
| `ns/packet/rate_sample.py` | 122 / 89 / 21 / 12 | 115 / 79 / 21 / 15 |
| `ns/packet/bbr_generator.py` | 400 / 318 / 56 / 26 | 416 / 329 / 59 / 28 |
| Total | 835 / 644 / 105 / 86 | 806 / 621 / 111 / 74 |

Net production change: **-29 physical, -23 code-bearing, +6 explanatory, -12
blank lines**. Inline comments change from seven to one. The controller removes
unused timestamped slot wrappers and misleading v3 scaffolding; the sampler
removes duplicated rate initialization and unused scratch fields. The sender
adds two small helpers to keep new-send/retransmit snapshots consistent and
explain unlimited-source classification. Units, timing, loss frontiers, and
model omissions have direct comments or docstrings; no execution framework or
new transport abstraction is introduced.
