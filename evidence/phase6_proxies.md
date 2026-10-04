# Phase 6 proxy sockets

Accepted baseline: `65dfd2d` on `modernize-python314-correctness`. The requested
[harness](https://baochun.org/2026-09-05/) was read; this component task uses the
user's internal-agent override and adds no nested agents or task commits.

Current Days CPU has **no real-socket emulation counterpart**. These results are
independent local socket/lifecycle invariants, not a claimed Days comparison.

## Audited behavior

| Component | Disposition and observation |
| --- | --- |
| `packet/proxy_generator.py` | Actual payload lengths, unique lifetime flow IDs, TCP full writes/EOF, UDP return routing and whole/empty datagrams, all closed sockets retired; tested. |
| `packet/proxy_sink.py` | One connected socket per TCP/UDP flow preserves return identity; full TCP writes, server EOF propagation, failed-connect descriptor cleanup, bounded socket timeout and delayed close tested. |
| Shared proxy polling | Replaces untracked per-packet timer threads with the existing SimPy process and a small heap; positive/cooperative waits, FIFO deadline ties, delayed-data-before-close and explicit cancellation tested. |
| Sink statistics | Reuses `PacketSink` instead of copying accounting; observed data bytes/counts, independent per-hop snapshots, and exclusion of EOF control packets tested. |
| `examples/real_traffic/proxy.py` | Lifecycle inspection; `try/finally` closes both proxies. No interactive or external traffic was started. |

Constructors, imports, `put()`/`out` composition and counters remain available.
Intentional behavior changes and timing/lifecycle constraints are described in
[Local socket proxies](../docs/proxies.md). Packet sizes represent received bytes;
TCP receives are stream chunks, UDP receives preserve datagrams independent of
the TCP buffer limit. EOF uses `payload=None`; empty UDP bytes remain data.

## Red/green evidence

Before production edits, the initial six focused cases all failed against the
accepted Phase 5 proxy files: two inflated-size assertions, generator UDP client
identity, sink UDP source/return identity, aliased per-hop statistics, and a
negative timeout when the simulation starts at `t=10`. After the repair, all six
passed. TCP EOF/unique packet IDs are later assertions in those same observable
payload tests, not assertions of private implementation state.

Additional tests run against the accepted files reproduced one-byte partial
writes in **both** TCP proxy directions and removal of only one externally
closed flow. Deterministic refused/timed-out connection injections separately
reproduced an open descriptor after refusal and an attempted write on an
unconnected socket after timeout. Both now close the descriptor and propagate
the original connect failure. During implementation, two UDP cases reproduced
silent truncation of a 14-byte datagram with `packet_size=3`; both now preserve
all 14 bytes. These observations establish separate failures, rather than
counting every assertion as an independent bug.

Final focused suite also observes two actual loopback TCP server connections,
chunked responses and EOF for each flow; two UDP clients and server-side flows;
partial-write/timeout behavior; delayed data preceding an already-due EOF; no
socket or connection creation after explicit shutdown; and an idle sink that
advances simulation time without passing an empty descriptor set to `select`.
The delayed-send tests inject a monotonic clock while using actual socket pairs.
All socket receives have one-second timeouts, observation stepping has finite
wall deadlines, and all owned sockets are released in `finally` blocks. No
production thread, external server, fixed listening port, or unbounded test
worker is used.

```sh
uv run --locked pytest -q tests/packet/test_proxy_io.py tests/packet/test_sink.py
# 23 passed in 0.13s (19 proxy cases and 4 PacketSink cases)

git diff --check -- ns/packet/proxy_generator.py ns/packet/proxy_sink.py examples/real_traffic/proxy.py docs/proxies.md tests/packet/test_proxy_io.py
# Exit 0
```

Phase integration, exact candidate-commit review, full tests, example smoke
checks and package validation remain the orchestrator's gate.

## Limits and readability

This small adapter uses plain SimPy plus approximately 10 ms socket polling.
It does not implement TCP half-close, socket admission limits, retransmission
inside a simulated lossy/reordering path, or UDP inactivity expiry. UDP resources
last until `close()`. TCP connect/send timeouts are one second after system
address resolution; numeric loopback destinations avoid an unbounded DNS lookup.
A timed-out full write may already have sent a prefix; the flow terminates rather
than replaying it. Sink statistics report simulated arrival rather than confirmed
remote consumption. Explicit shutdown releases descriptors and queued sends
immediately; its polling process exits at the next scheduled wakeup.

Counts use AST docstring ranges and comment-only nonblank lines as explanatory;
remaining nonblank physical lines are code-bearing, including delimiters. Inline
comments count as code-bearing. This reports source size, not executable statement
count or complexity.

| Owned production | Accepted physical/code-bearing/explanatory/blank | Candidate physical/code-bearing/explanatory/blank |
| --- | --- | --- |
| `proxy_generator.py` | 230 / 166 / 28 / 36 | 235 / 176 / 31 / 28 |
| `proxy_sink.py` | 268 / 185 / 39 / 44 | 91 / 65 / 13 / 13 |
| `examples/real_traffic/proxy.py` | 55 / 40 / 5 / 10 | 61 / 44 / 6 / 11 |
| Total | 553 / 391 / 72 / 90 | 387 / 285 / 50 / 52 |

Net production change: **-166 physical, -106 code-bearing, -22 explanatory,
-38 blank lines**. The 379-line test module has 326 code-bearing, 7 explanatory,
and 46 blank lines. Shared polling removes duplicated socket/statistics loops;
comments explain bytes, monotonic seconds, cancellation, EOF, timeout uncertainty,
and insertion order. No asynchronous server framework or new execution engine
was introduced.
