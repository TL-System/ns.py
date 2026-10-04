# Phase 5 Reno and shared feedback implementation

Baseline: accepted Phase 4 `18c6de4`, Python **3.14.8**. Read-only algorithm
reference: Days `9ff20eac16dcdf752510b05cbcf526684dc05146`,
`executor/src/tcp.rs` (`TcpReno` feedback transitions). This task does not claim
actual CPU equivalence; the separate CPU-reference task must record execution
and compare its transitions and full flows.

Reno now counts bytes. Slow start adds the smaller of one MSS and newly ACKed
bytes, stopping exactly at the threshold. Congestion avoidance earns one MSS
after acknowledging the current window, retains unused credit, and charges the
larger window after each increase. This intentionally replaces the previous
per-ACK fractional approximation. Timeout and fast loss use actual pre-feedback
flight, with a two-MSS threshold floor; direct calls without transport context
fall back to the current window. Actual zero flight remains distinct from absent
context. Loss and recovery exit clear avoidance credit. A partial recovery ACK
sets Reno's window to threshold plus one MSS; a full exit ACK deflates to the
threshold without ordinary ACK growth.

Classic TCP sends the exact cumulative frontier delta through
`ack_received_bytes(bytes, rtt, now)`. The base adapter preserves controllers
implementing the older two-argument callback; duck-typed controllers without
the adapter retain their existing callback and estimator-value fallback.
Loss-based controllers receive explicit ACK bytes, with `ack_received()` still
defaulting to one MSS for direct use. A fresh RTT sample can be numeric zero;
`None` means Karn declined a fresh sample. The legacy base adapter maps `None`
to its old zero convention. Recovery hooks retain their Phase 4 signatures and
sampling limits. Controllers consume flight context after feedback, and the
sender supplies no unused context on the first two duplicate ACKs.

Known alignment limits: Python retains floating-point windows, so halving odd
flight can retain half a byte where Days floors integer division. The shared
two-MSS floor and feedback decisions are unchanged; aligned exact fixtures
should use even flight sizes, with odd-flight differences bounded by half a
byte for that reduction. Python constructors retain the existing one-MSS
initial window; fixtures must explicitly choose Days's two-MSS initial window
and threshold. Python has unbounded numeric byte counters instead of Days's
saturating `u64` counters. RTT ambiguity, event ordering, serialization rounding,
and observation boundaries remain documented in [TCP timing](../docs/tcp_timing.md).

Red/green evidence:

- Before the controller repair,
  `uv run --locked pytest -q tests/flow/test_reno.py` reported **16 failed,
  2 passed**. Failures include the old fractional growth, incorrect loss
  thresholds, and partial recovery; explicit byte feedback was absent.
- After the controller repair, replaying the accepted Phase 4 sender module in
  memory against the new short-final, cumulative-feedback, zero-RTT bridge,
  and unused-context tests reported **4 failed, 10 deselected**. The receiver
  delivered 701 bytes, but the old sender inflated Reno from 300 to 1200 bytes
  instead of 1001. The cumulative/zero-RTT bridge had no observations; unused
  duplicate-ACK context caused a later direct loss to halve stale flight.
  Replay used `git show 18c6de4:ns/packet/tcp_generator.py`, executed in a
  `types.ModuleType` registered in `sys.modules`, followed by
  `pytest.main(['-q', 'tests/packet/test_tcp_generator.py', '-k',
  'reno_short_final or cumulative_ack_bridge or preserves_measured_zero or
  first_two_duplicate'])`; the checkout was not changed for the replay.
- Final scoped command:
  `uv run --locked pytest -q tests/flow/test_reno.py
  tests/flow/test_tcp_congestion.py tests/packet/test_tcp_generator.py
  tests/packet/test_tcp_transport.py tests/packet/test_tcp_transport_integration.py`
  — **93 passed**. `git diff --check` passed. Tests use hand-calculated byte
  traces, explicit loss/reordering, a real receiver, old custom callbacks, and
  observable retransmission/cleanup assertions. Root owns broader integration
  validation and fresh review of the exact candidate commit.

Production source growth relative to accepted Phase 4:

| File | Physical lines | Executable/declaration lines | Explanatory lines |
| --- | --- | --- | --- |
| `ns/flow/cc.py` | 182 → 238 (+56) | 90 → 127 (+37) | 57 → 73 (+16) |
| `ns/packet/tcp_generator.py` | 350 → 359 (+9) | 256 → 261 (+5) | 65 → 69 (+4) |

Counts use Python AST docstring ranges and tokenizer comment ranges. Code
counts non-layout token lines outside docstrings; explanatory counts include
comments and docstrings, so an inline comment can share a code line. The added
code supplies the compatibility bridge, consumable loss context, and explicit
byte credit; it adds no dispatch framework or transport timing model.
