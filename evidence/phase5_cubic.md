# Phase 5: CUBIC feedback audit

Candidate starts from accepted Phase 4 `18c6de439710369ae2fc9b6c699c819e3d9656a2`.
The primary comparison source is the current Days CPU controller at
`9ff20eac16dcdf752510b05cbcf526684dc05146`, inspected read-only in
`~/Playground/days/executor/src/tcp.rs` (`TcpCubic`, lines 408–539, and its
arithmetic helpers, lines 595–679). The current CPU executor uses these
transitions through its scalar transition code. No legacy-only behavior is
presented as current CPU behavior.

This task establishes independent equation and explicit feedback tests. It does
not establish an actual CPU replay by itself; the phase's recorded CPU fixtures
must supply that separate evidence before acceptance.

## Model and compatibility

`TCPCubic` implements the pinned Days educational CUBIC variant in floating-point
seconds and MSS-sized segments, exposing its congestion window in bytes.
[Current CUBIC specification, RFC 9438](https://www.rfc-editor.org/rfc/rfc9438.html)
obsoletes RFC 8312 and helps distinguish standard CUBIC from this model. The
previous claim that this class implements Linux CUBIC with RFC-compliant beta=0.2
was inaccurate and has been removed.

The default beta is now **0.7 retained**, rather than the old **0.2 removed**.
Explicit `beta` arguments also mean the retained fraction. This is an intentional
meaning change; preserving the old convention would make textbook equations and
comparison inputs misleading. Constructor argument order, class/import names,
byte window units, and `fast_convergence`/`tcp_friendliness` switches are preserved.
Obsolete ACK counters and minimum-RTT state are removed. `W_last_max` now records
the last observed pre-loss window; the distinct `W_max` is the curve origin.
`epoch_start=None` means no epoch, so an epoch beginning at simulation time zero
survives later ACKs.

With W in segments, t in seconds, C=0.4 and beta=0.7, the reference uses:

- After loss, `K=cbrt(W_max*(1-beta)/C)` and `W(t)=W_max+C*(t-K)^3`.
  A first no-loss avoidance epoch instead begins at current W with K=0.
- `W_est=beta*W_max + 3*(1-beta)/(1+beta)*t/SRTT`; the coefficient is 9/17.
  If W(t) is below this estimate, the next window is the estimate directly.
- Otherwise one advancing ACK applies `W += (W(t+SRTT)-W)/W`. This is a signed
  fractional step, including when the target is below the current window.
  Avoidance state persists even if such a step falls below ssthresh.
- Slow start adds `ceil(newly_ACKed_bytes/MSS)*MSS`. A short segment counts as
  one segment and a cumulative ACK can count several; the threshold crossing
  is not clipped. This differs from the Reno byte-counting rule.
- A loss below the last observed maximum sets the new curve origin to
  `current_W*(1+beta)/2`, or 17/20 of current W with defaults, and records
  current W separately as W_last_max. Other losses use current W directly.
- Fast retransmit reduces **actual outstanding bytes**, not cwnd, to beta times
  flight with a one-MSS cwnd floor and two-MSS ssthresh floor. Unlike Reno it
  does not add three MSS at entry. Extra dupACKs add one MSS only in recovery;
  partial recovery ACKs hold cwnd. Exit sets cwnd to ssthresh and preserves the
  epoch established at loss time.
- Timeout uses beta times actual flight with the two-MSS threshold floor,
  reduces cwnd to one MSS, erases both maxima/K/epoch, and resumes slow start.
  It retains the RTT estimate.

The transport supplies time and flight through the existing `set_before_control`
hook; direct calls without flight information use cwnd as a compatibility
fallback. Each feedback handler consumes that flight context. The shared
`ack_received_bytes` adapter carries exact ACK byte counts. Direct
`ack_received(rtt, time)` calls still mean one MSS; explicit `rtt=None` means no
new measurement. True zero RTT samples are valid but the controller floors them
at one nanosecond for its SRTT/denominator, as Days does; this does not quantize
SimPy's clock. Fresh SRTT updates use `(7*old+sample)/8`.

This variant deliberately omits RFC 9438's fuller Reno-friendly and slow-start
machinery, Linux implementation state, idle/application-limited epoch adjustment,
and SACK/ECN. Phase 4 conservative Karn sampling stays in force: ambiguous normal
ACKs leave SRTT unchanged, and partial/exit recovery callbacks supply no RTT
sample. Days instead updates its controller RTT from echoed samples even during
recovery. Align primitive feedback observations when comparing equations; full
flows with ambiguous/recovery ACKs can have different SRTT and subsequent windows.
This is a documented measurement difference, not numeric quantization.

Days rounds K down to integral nanoseconds, uses decimal nanosegment windows,
and exposes whole-byte windows. Python retains fractional bytes, float RTT
samples and curve calculations. Both bound curve/window state to one through
2,000,000 segments (the two-MSS threshold floor is separate). At t=0 after
loss, Python evaluates `beta*W_max` directly to avoid cube-root rounding
changing the friendly-region decision at mathematical equality. Compare
controller transitions first and justify numerical error for each recorded
fixture; do not impose byte-identical windows or use a broad tolerance to hide
changed recovery decisions.

## Reproducers and validation

The initial `uv run --locked pytest -q tests/flow/test_cubic.py` produced **15
failures and 1 pass** on the Phase 4 implementation. Failures covered beta/loss
entry, ACK-byte input, threshold crossing, zero-time epoch, fractional ACK growth,
SRTT rather than minimum RTT, friendly growth, separate convergence maxima,
actual-flight reduction, signed decrease, recovery behavior, and timeout reset.
The existing end-to-end loss smoke passed before the changes and remains a
composition regression rather than a new bug reproducer.

The zero-time cubic test disables the optional friendly branch to isolate the
curve. During development its initial second-ACK expectation omitted the
friendly-region condition; that expectation was corrected before final
validation. Additional tests distinguish no RTT sample from true zero, and check
explicit custom-beta meaning. Expectations are hand-calculated equations and
feedback sequences, not snapshots of implementation counters.

Commands:

- `uv run --locked pytest -q tests/flow/test_cubic.py tests/flow/test_tcp_congestion.py tests/flow/test_tcp_integration.py tests/packet/test_tcp_generator.py`
- `uv run --locked python scripts/smoke_examples.py`
- `git diff --check`

The first command passes **38 tests** after the shared Reno historical assertion
is updated to its independently tested byte-credit behavior. The CUBIC-specific
suite contains **18 passing cases**. Its finite-flow smoke drops the first data
attempt with MSS=1000, cwnd=4000, ssthresh=4000, data volume=8123, and 10 ms delay
in each direction. It verifies one retransmission of the first 1000-byte range,
the exact short final segment, 8123 contiguous delivered bytes, empty outstanding
state, and no subsequent delivery change through simulation time 10 seconds.
The curated basic, TCP, and FatTree examples all pass (approximately 0.06 s,
0.07 s, and 10.9 s in this run).

## Source size and readability

Compared with Phase 4 using Phase 0's AST/token categories. Explanatory lines are
nonblank docstrings and comment-only lines; code-bearing lines include other
nonblank lines and delimiters. Inline comments overlap code-bearing lines.

| `ns/flow/cubic.py` category | Before | After | Change |
| --- | ---: | ---: | ---: |
| Physical | 143 | 176 | +33 |
| Code-bearing | 93 | 119 | +26 |
| Explanatory | 30 | 37 | +7 |
| Blank | 20 | 20 | 0 |
| Inline comments | 1 | 2 | +1 |

The class directly expresses the curve, estimate, and loss/recovery transitions.
Two booleans retain the familiar slow-start/avoidance/recovery distinction
without a new framework; each state variable has units and purpose nearby.
The new CUBIC test file has 198 physical lines, 156 code-bearing, 5 explanatory,
and 37 blank; test/evidence growth is separate from production growth. Shared
transport/base-controller growth belongs to the Reno task's evidence.
