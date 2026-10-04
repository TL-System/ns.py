# Phase 6: traffic sources, Flow, and mathematical generators

Base: accepted Phase 5 `65dfd2d6b322cbae91eed20772d0780d2725d6ba`.
Reference: current Days `9ff20eac16dcdf752510b05cbcf526684dc05146`,
read from `/Users/bli/Playground/days`; that checkout was not modified.
The task retains the existing SimPy processes and `out.put(packet)` composition.
No application framework, sender-mechanics change, or random-seed equivalence
claim is involved.

## Inventory closure

| Inventory module | Audit and evidence |
| --- | --- |
| `packet/dist_generator.py` | Explicit start, exclusive finish, exact byte budget, packet IDs/counts, source-owned accounting, simultaneous/zero-byte packets, invalid draws; `tests/packet/test_dist_generator.py` plus the CPU tape replay in `test_trace_generator.py`. |
| `packet/trace_generator.py` | Both row formats, whitespace, source-relative timestamps, equal-time order, exclusive finish, nondecreasing finite times, zero-byte packets, empty/end-of-file behavior; `tests/packet/test_trace_generator.py`. File ownership inspected: `with open(...)` closes on EOF, finish, and parsing failures. |
| `flow/flow.py` | Bulk/unlimited conventions, retained streaming arrival, exact polling boundary, start/finish/volume, zero-byte arrivals, and rejection of nonadvancing intervals; `tests/flow/test_flow.py`. Dataclass configuration fields and `__repr__` inspected; no sender uses these helpers after the accepted transport repairs. Tuple-valued enum declarations corrected to ordinary `auto()` values; enum member identities remain unchanged. |
| `utils/generators/MAP_MSP_generator.py` | CTMC/DTMC balance, shapes/signs/finite rates, silent transitions, batch choices, initial phase, absorption, finite zero-endpoint holding time; `tests/utils/generators/test_map_msp.py`. `sum_matrix_list` is exercised by balance and stationary-initialization cases; it does not mutate inputs. |
| `utils/generators/pareto_onoff_generator.py` | Inverse Pareto CDF, valid scale/shape, seconds-versus-packets correction, bytes-to-bits spacing, on-period endpoint, short bursts and unsent on-period tail; `tests/utils/generators/test_pareto_onoff.py`. Mean formula inspected against the distribution equation below. |

## Behavior and simple timing rules

`DistPacketGenerator` emits its first packet after `initial_delay`, without an
interarrival draw first. `finish` is an absolute, exclusive time. A finite `size`
is a total byte budget: 100-byte draws with budget 150 emit 100 then 50 bytes.
Completion consumes no unnecessary interval draw or future wait. A wait that
crosses finish ends at finish without another packet. Source counters/records
are registered before synchronous forwarding; changing the forwarded packet's
size or timestamp cannot change the source's budget or historical telemetry.

Both packet sources retain zero-byte packets. A distribution may return zero
intervals for a simultaneous burst; each Dist iteration still yields a SimPy
timeout. As with any unbounded traffic source, caller distributions must
eventually advance simulated time, and a finite byte budget requires eventual
byte progress. We do not try to prove arbitrary user callables terminate.
Generated Dist intervals and sizes must be finite and nonnegative. `None`
continues to mean an unbounded Dist finish/byte budget. The existing basic
example can round an exponential size to zero, which remains valid.

Trace timestamps are seconds relative to source start, including initial delay.
The two formats remain `flow_id packet_id time size` and, when a fixed flow ID
is supplied, `packet_id time size`. Leading/trailing whitespace is harmless.
Times must be finite, nonnegative and nondecreasing; equal times retain file
order. A future row is checked against finish before waiting, so rows at or
after finish cannot escape. No new CSV parser, preload stage, or trace framework
was added. Invalid row shapes/conversions use ordinary Python `ValueError`.

Flow's optional streaming helper retains one pending arrival rather than
redrawing at every poll. With intervals 2, 3, 4, polls at 0, 1, 2, 4, 5, 5
return 0, 0, 100, 0, 100, 0 bytes for 100-byte draws. Its first arrival is one
interval after `max(last_arrival, start_time or 0)`. An arrival exactly at the
poll time is ready; an arrival exactly at finish is excluded. A finite flow
size caps cumulative generated application bytes. A zero-byte arrival still
advances the arrival clock. The synchronous catch-up loop requires positive,
finite intervals and checks that floating-point addition actually advances its
clock. Bulk initialization retains `size`, including the existing `None`
unlimited sentinel; subsequent bulk polls return zero. TCP/BBR continue to own
their already accepted sender-local application scheduling.

For MAP/BMAP, `D0` contains silent transitions and negative holding-rate
diagonals; `Dk` contains nonnegative rates for batches of size `k`.
Their sum has zero row sums, within the existing `1e-5` absolute tolerance.
Every phase must reach an arrival through positive-rate silent transitions.
A finite graph reachability check rejects closed silent classes without relying
on the sign of a numerically near-zero eigenvalue. Each step's mean holding
time is `-1 / D0[state,state]`; transition probabilities are rates times that
holding-time mean. Probabilities are normalized only for the accepted row-sum
rounding tolerance, and cumulative selection ends at exactly 1.

The deterministic two-phase test silently transitions at rate 2, then emits at
rate 4. Injected uniforms `exp(-1)` and `exp(-2)` imply waits 1/2 and 2/4,
so the emitted interval is exactly one second. The one-state batch test has
rate-1 singleton arrivals and rate-3 batches of two: its batch boundary is
1/4, with an exact-boundary draw choosing the second batch interval. The
stationary solver independently gives `(0.6, 0.4)` for rates 2 and 3, satisfying
both `pi Q = 0` and the corresponding `pi P = pi` equations.

The sampler's existing default initializes from the stationary distribution of
the underlying CTMC at a time origin. Its first sample is consequently a
stationary-time residual, not an arrival-stationary interval; subsequent samples
start at arrivals. Callers may specify an initial phase. If stationarity is not
unique, the solver raises a clear `ValueError`; explicit initialization still
supports valid disconnected arrival classes. The zero uniform endpoint is
clipped to the smallest positive float before logarithm, so it cannot create
an infinite holding time merely from `log(0)`.

The independent mathematical references are BuTools'
[MAP representation conditions](https://raw.githubusercontent.com/ghorvath78/butools/master/Python/butools/map/check.py)
and [phase-holding/transition sampler](https://raw.githubusercontent.com/ghorvath78/butools/master/Python/butools/map/misc.py).
The implementation keeps the recognizable small rate-matrix sampler and does
not introduce another numerical library.

Pareto durations use `F(x) = 1 - (xmin / x)**alpha`; inversion is
`xmin / (1-U)**(1/alpha)`. Scale and shape must be finite and positive.
The mean is `alpha*xmin/(alpha-1)` for `alpha > 1`, and infinite for
`alpha <= 1`. This follows directly by integrating the density documented in
the [SciPy Pareto reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pareto.html).
Tests inject a quantile (`U=0.75`, scale 3, shape 2 gives 6) rather than
estimating a heavy-tail mean with a large stochastic test.

On/off draws describe seconds, not packet counts. With 1000-byte packets at
8000 bits/second, spacing is one second. An on duration 2.5 and preceding off
duration 4 emits at 4, 5, 6; the remaining 0.5 seconds of on time plus a
3-second off period puts the next burst at 9.5. An exact one-second on period
with 0.5-second spacing contains packets at its beginning and midpoint, with
the endpoint excluded. Even a short on period emits its first packet at the
on-period start; this is an explicit packetization convention, not a continuous
fluid-rate envelope. The iterator starts with an off interval. When plugged
into Dist, Dist's own initial packet precedes that first interval as it always
has; the generator docstring makes that composition convention explicit.

## Current Days CPU comparison and gaps

Inspected current `executor/src/scalar.rs` constant generation and
`host_preloaded_packet_arrival`, `executor/src/image.rs` `ConstantGenerator`,
`GeneratorTermination` and `FlowGeneratorState`, `src/scenario/compile.rs`
constant distribution lowering, and `src/utils/testgen/trace.rs` CSV utilities.
Current CPU uses the inspected Scalar transitions; Scalar-only inspection is
not presented as an executed CPU comparison.

The new parametrized tape replay consumes the existing recorded **actual CPU**
fixture `tests/reference/days_fifo.json`, with pinned revision and provenance
retained by the Phase 2 helper. Both Trace and Dist feed its five exact inputs
to the ns.py FIFO Port. Dist's consecutive source IDs are explicitly translated
to the fixture identities; Trace preserves its listed identities directly.
Both produce departure identities 0, 3, 6, 9, 12 at 1000, 1500, 1750, 2500,
5125 ns and conserve 2625 bytes. The existing one-femtosecond bound covers only
floating-point accumulation; packet order and byte counts are exact. The finite
Python scenario is drained. This extends source-to-Port coverage using the
retained CPU fixture; it does not regenerate the same Rust result or claim the
CPU compiler supports every distribution accepted by Python.

Days constant duration termination is exclusive, matching source finish
semantics; its global engine stop is inclusive. Current constant byte
termination sends full constant-size packets until total bytes reach or exceed
the target. Python now emits an exact short final packet, so a nonmultiple byte
budget is a documented difference. Days scenario lowering accepts constant
packet-size/interarrival distributions and rejects zero interarrival intervals;
Python retains callable distributions and finite simultaneous bursts.
The CSV helper is not a matching whitespace Trace API. Current CPU has no
direct MAP/BMAP or Pareto on/off implementation and no matching polling Flow
helper. Those gaps are closed by the independent timing/mathematical tests,
not legacy-output equivalence or matching seeds.

## Red/green validation

The initial focused tests ran before production edits: 44 failed, 12 passed.
Failures exposed excess final bytes/extra draws, finish waits/trace emissions,
Flow redraws/strict boundaries, invalid matrices/initial phases, and on-duration
unit errors. Later ownership and clock-precision tests each failed before their
corresponding repair. Final test files were also replayed against all five
accepted Phase 5 modules **in memory**, without changing the shared working
tree: **48 failed, 15 passed**. Reproduce that comparison with:

```sh
uv run --locked python - <<'PY'
import importlib
import subprocess
import pytest
paths = ['ns/flow/flow.py', 'ns/packet/dist_generator.py',
         'ns/packet/trace_generator.py',
         'ns/utils/generators/MAP_MSP_generator.py',
         'ns/utils/generators/pareto_onoff_generator.py']
for path in paths:
    module = importlib.import_module(path[:-3].replace('/', '.'))
    source = subprocess.check_output(['git', 'show', f'65dfd2d:{path}'], text=True)
    exec(compile(source, f'65dfd2d:{path}', 'exec'), module.__dict__)
raise SystemExit(pytest.main(['-q', '--tb=no',
    'tests/packet/test_dist_generator.py', 'tests/packet/test_trace_generator.py',
    'tests/flow/test_flow.py', 'tests/utils/generators']))
PY
```

Final targeted regression command:

```sh
uv run --locked pytest -q tests/packet/test_dist_generator.py \
  tests/packet/test_trace_generator.py tests/flow/test_flow.py \
  tests/utils/generators tests/packet/test_tcp_generator.py \
  tests/packet/test_bbr_generator.py
MPLBACKEND=Agg uv run --locked python examples/basic.py
MPLBACKEND=Agg uv run --locked python examples/bursty_traffic_generation.py
git diff --check
```

Result: **85 passed**, including **63 focused source/Flow/generator cases**.
Both examples passed; the bursty plot emitted only the expected headless Agg
warning. Python is 3.14.8. Pytest emitted pre-existing cleanup warnings about
unrelated temporary read-only model directories; no task resources were removed
to silence them. Full-suite/smoke/build integration remains the phase gate's work.

## Production size and readability

Counts compare the five owned production files with accepted Phase 5. Nonblank
docstring and comment-only lines are explanatory; other nonblank lines are
code-bearing, including declarations and delimiters. Inline comments belong to
the code-bearing category. This is a source-size proxy, not statement complexity.

| Module | Accepted physical/code/explanatory/blank | Candidate physical/code/explanatory/blank |
| --- | --- | --- |
| Flow | 52 / 39 / 2 / 11 | 81 / 58 / 12 / 11 |
| Dist | 97 / 54 / 30 / 13 | 124 / 71 / 39 / 14 |
| Trace | 75 / 61 / 1 / 13 | 93 / 71 / 9 / 13 |
| MAP/BMAP | 131 / 76 / 29 / 26 | 135 / 88 / 29 / 18 |
| Pareto on/off | 67 / 25 / 33 / 9 | 88 / 33 / 45 / 10 |
| Total | 422 / 255 / 95 / 72 | 521 / 321 / 134 / 66 |

Net production growth: **66 code-bearing**, **39 explanatory**, **99 physical**
lines, with six fewer blank lines. The two streaming state fields represent the
pending arrival and cumulative bytes; no parallel application object was added.
Matrix input checks are shared by one small square-matrix helper. The sampler
removes repeated manual cumulative searches/printing, and Pareto on/off now uses
seconds directly. Comments explain timing, packetization, units and ownership.
