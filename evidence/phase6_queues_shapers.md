# Phase 6: RED, token buckets, and three-color marking

The task starts from accepted Phase 5 `65dfd2d`. Reference inspection is against
Days `9ff20eac16dcdf752510b05cbcf526684dc05146`, read-only in
`~/Playground/days`. This task edits four production modules and does not change
the accepted Port or scheduler release contracts.

## Audit closure and models

| Module | Audit and independent evidence |
| --- | --- |
| `ns/port/red_port.py` | Unlimited/zero/exact-fit admission semantics inherit Port; resident accounting, pre-arrival EWMA, min/max boundaries, explicit draws, idle behavior, capacity precedence, retained downstream composition, and invalid settings are tested. |
| `ns/shaper/token_bucket.py` | Bit/s rates, byte bursts, FIFO timing, idle refill, mixed/oversized packets, peak serialization, ordinary rate/burst envelopes, busy state, and reordered retained ownership are tested. |
| `ns/shaper/two_rate_token_bucket.py` | Optional PIR/PBS pairing, peak gating, committed credit preservation/refill, service-start colors, no-PIR CIR gating, green/peak envelopes, oversized borrowing, and retained ownership are tested. |
| `ns/utils/misc.py` (`TrTCM`) | RFC 2698 section 3 color-blind marking, initial full buckets, exact fits, idle caps, byte/bit conversion, precolor overwriting, unchanged flow identity, red consuming neither bucket, and invalid configuration are tested. |

All four owned inventory rows are closed. Neither the shapers nor TrTCM has a
direct current Days CPU counterpart. Their independent specification/invariant
tests establish the behavior; historical Days output is not claimed as parity.

### RED: shared rules and explicit differences

Current Days `executor/src/model.rs` defines `RedPolicyState`; the CPU backend
uses the scalar transition code. `executor/src/scalar.rs:6614` implements its
arrival-sampled RED decision:

- With scale S=2^32, `A' = floor((511*A + sample*S)/512)` on every arrival,
  including arrivals rejected by capacity.
- Capacity compares the post-arrival depth, accepting an exact fit, before the
  congestion signal decision. At/below minimum no signal occurs; at/above
  maximum signaling is unconditional. Between thresholds, the probability
  ramp is `max_p * (average-min)/(max-min)`.
- Days counts waiting packets/bytes and uses deterministic counter signaling
  (`counter*p >= 1`), optionally marking ECN. Its capacity zero means unlimited.

Python retains independent random draws, floating-point averages, configurable
`alpha=2**(-weight_factor)`, and no ECN/count-correction feature. Default alpha is
1/512. Sampling now occurs before the arriving packet, with the same recurrence
order and threshold rules as the inspected model. Python samples **residents**,
including local service and downstream retained packets, because that is Port's
accepted accounting. It uses `None` for unlimited capacity and zero for no
capacity. Equal numeric queue limits therefore do not in general align capacity
with Days; an in-service packet adds a resident in Python but not a waiting slot
in Days. Averaging measurements also require explicit alignment before comparing
a drop decision.

Both implementations update only at arrivals. Wall-clock idle time does not
trigger extra decay; the next empty-queue arrival contributes one zero sample.
This is an intentional simplified model, rather than the full classic RED idle
decay procedure. Above the maximum, Python now always drops rather than clipping
the probability at max_probability. Below the maximum it uses `draw < p`, so
probability zero cannot drop a draw of zero and a draw exactly equal to p admits.

Tests use draws .24 and .25 for p=.25 and require the later maximum-threshold
drops to consume no additional draws. A hard-capacity overflow also consumes no
draw, while still updating the average. A default-weight empty/one-resident
fixture verifies average 1/512. EWMA samples 0,1,2 with alpha=.5 independently
give averages 0,.5,1.25. Byte samples include the existing packet sizes; packet
samples use accepted minus released counts, surviving pending Store.get handoffs.

Days' `executor/tests/aqm_semantics.rs` separately documents its deterministic
sequence and contains `aqm_checkpoint_and_cpu_worker_matrix_match_scalar`, using
actual CPU workers 1/2/4. These reference tests were inspected, not executed in
this task. No Python/current CPU packet-drop identity replay is claimed: random
versus deterministic signaling is an explicit comparison gap.

### Shapers and marker

Rates are bits/second; refill adds `rate * seconds / 8` byte tokens, while
serialization waits `packet_bytes * 8 / rate`. Constructors reject nonfinite or
nonpositive gating rates/burst capacities and incomplete/impossible optional
peak settings. Token buckets start full when constructed and cap idle refill.

Single-rate shaping consumes available credit or waits for the deficit. Optional
peak service delays departure; that service time also replenishes tokens for the
next head packet. A 100-byte bucket at 800 bit/s emits queued sizes
60,40,20,200,10 at times 0,0,.2,2.2,2.3 seconds. With peak=400 bit/s, three
100-byte packets depart at 2,4,6 seconds. Every contiguous departure window of
ordinary packets is tested against `bytes <= burst + rate_bytes*elapsed`.

Two-rate shaping preserves the existing API's **eligibility at service start**
colors. With PIR, a packet fitting both buckets is green and consumes both;
one fitting peak but exceeding committed credit is yellow and consumes only
peak; one needing a peak wait is red and consumes the waited-for peak tokens.
Yellow/red preserve committed credit, and a peak wait replenishes that credit.
Only PIR gates total traffic, while green traffic has the CIR/CBS envelope.
Without PIR, CIR gates all traffic and a wait is yellow. These colors are not
RFC arrival metering colors. For CIR=80,CBS=10,PIR=800,PBS=100, sizes 5,95,100,10
depart at 0,0,1,1.1 with green,yellow,red,red, leaving 10 committed byte tokens.
An additional timed-arrival case verifies peak and green envelopes independently.

Both shapers preserve the compatibility policy for packets exceeding the gating
bucket: wait for the excess at its rate, then leave zero credit. This admits
large packets but relaxes the ordinary burst envelope for that packet; tests
separate borrowing from the envelope tests, whose packets fit their buckets.
A peak bucket of 100 bytes at 800 bit/s sends sizes 250 and 1 at 1.5 and 1.51
seconds. There is no silent deadlock or unbounded negative token debt.

TrTCM remains color-blind, as its existing API is: previous packet.color is
overwritten, and packet.flow_id is preserved. RFC 2698's color-aware mode is
outside this implementation's scope. RFC rate values are bytes/second, while
this API takes bit/s. Buckets start full; red consumes neither, yellow only
peak, green both, and exact fits conform. It neither delays nor drops arrivals.
The old comments incorrectly claimed numeric colors in flow_id; the implementation
already used string colors in packet.color, and its valid color-blind transition
logic is retained. Configuration validation and teaching comments now agree with
[RFC 2698 sections 2–3](https://www.rfc-editor.org/rfc/rfc2698).

Shared ownership uses the existing `remove_packet` helper. Hooks are popped
before callbacks and repeated release is harmless. Direct zero-buffer input
without upstream hooks is accepted. Port → shaper → priority scheduler tests
first establish nonpreemptive service, then enqueue low/high packets. Departures
and releases are first,high,low; both retained stores contain low after high
completes, and byte accounting reaches zero exactly once. The original FIFO
`upstream_store.get()` incorrectly released low while completing high.

## Validation and red/green evidence

Commands and results:

- Before production edits, `uv run --locked pytest -q tests/port/test_red_port.py tests/shaper tests/utils/test_trtcm.py --tb=no`: **46 failed, 6 passed** for the then-current 52 cases.
- Final 56 cases replayed with isolated `ns/` copies of the four modules from
  `git show 65dfd2d:<module>`, running the current tests via `.venv/bin/python -m
  pytest -q --tb=no --import-mode=importlib` with PYTHONPATH set to that temporary
  copy: **46 failed, 10 passed**. This does not mutate the shared working tree.
- `uv run --locked pytest -q tests/port tests/shaper tests/utils/test_trtcm.py tests/scheduler/test_composition.py`: **120 passed** after the final edits.
- A bounded `uv run --locked python` subprocess harness ran each of
  `examples/token_bucket.py`, `examples/two_rate_token_bucket.py`, and
  `examples/red_wfq.py` with `MPLBACKEND=Agg`, timeout=90 seconds, and an
  auto-cleaned temporary working directory: **all exit 0**. No generated plots
  were left in the repository.
- `git diff --check`: passes.

The tests' expected timings, decisions, colors, identity, and envelopes are
independent observable behavior. Constructor rejection tests complement these
behavioral cases. Development corrected the initial composition fixture by
starting service before later arrivals: simultaneous admission of all packets
correctly permits priority to choose high first and is not a scheduler defect.

## Source size and educational readability

Counts use Phase 0's physical-line categories: nonblank AST docstrings and
comment-only lines are explanatory; other nonblank lines are code-bearing;
inline comments overlap code-bearing lines and are reported separately.

| Production module | Physical before → after | Code-bearing before → after | Explanatory before → after |
| --- | ---: | ---: | ---: |
| `port/red_port.py` | 164 → 102 | 90 → 68 | 57 → 23 |
| `shaper/token_bucket.py` | 153 → 162 | 94 → 95 | 41 → 46 |
| `shaper/two_rate_token_bucket.py` | 179 → 203 | 115 → 129 | 47 → 53 |
| `utils/misc.py` | 64 → 59 | 30 → 36 | 24 → 15 |
| **Total** | **560 → 526 (-34)** | **329 → 328 (-1)** | **169 → 137 (-32)** |

Blank lines total 62 → 61; inline comments total 11 → 8. The reduction in RED
and marker boilerplate removes duplicated admission branches and inaccurate
parameter prose while placing the sampling, threshold, units, color, borrowing,
and ownership explanations directly beside the relevant process. Shaper growth
is local validation, busy telemetry, and correct retained/token bookkeeping;
there is no new framework. The three new test files total 457 physical lines,
374 code-bearing, 6 explanatory, and 77 blank, with 5 inline comments. Test and
evidence growth is separate from production size.
