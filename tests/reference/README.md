# Current Days CPU reference fixtures

Ordinary Python tests read `days_fifo.json`; Rust and a Days checkout are only
needed to regenerate it. This is one hand-built FIFO case, not a simulator
adapter framework. `days_fifo.rs` calls the public `run_cpu_with_observations`
API with `ObservationMode::Full` and two workers, and emits its actual departure
and arrival records. A full Scalar-result comparison is a secondary assertion.

Replay with the clean, pinned Days revision:

```sh
uv run --locked python tests/reference/regenerate_days_fifo.py \
  --days-root /path/to/days
uv run --locked pytest -q tests/port/test_days_fifo.py
```

The wrapper checks the revision and tracked-file cleanliness, creates a temporary
Cargo project with a path dependency on `days-executor`, copies the retained
helper lockfile, and runs Cargo with `--locked`. It removes its build directory
when finished and leaves both Days source and build output untouched. Use
`--output /tmp/days_fifo.json` to review regenerated observations before replacing
the recorded fixture.

Packets arrive directly at switch node 1, in the listed order; route link 0 is
metadata for the already completed source hop. Link 1 serializes at 8 Gbit/s and
propagates for 100 ns to terminal host 2. Queue capacity 0 in Days and `qlimit=None`
in ns.py both permit this unbounded case. Finite capacities are deliberately not
compared here: Days counts waiting packets, while ns.py counts service as well.
The packets cover simultaneous arrivals, arrival during service, arrival at a
service completion, and restart after an idle period. Sizes make every
serialization interval an integral number of nanoseconds.

Days includes its 5225 ns stop time, which is the last delivery. The Python test
drains all events for this finite case so it includes that delivery; the test
also asserts the drain ends at the same cutoff. Selection identity is exact.
The 0.000001 ns timing tolerance covers floating-point accumulation only and
rejects even a one-nanosecond difference. Global admission/delivery trace order
is not compared across unrelated links.

The reference revision, replay command, compiler version, helper source and
dependency-lock hashes, explicit input, and actual CPU output are recorded in
the JSON. See `evidence/phase2_reference.md` for executed commands and results.

## Current Days CPU scheduler fixtures

The same wrapper regenerates the recorded SP, DRR, and WFQ cases with
`--case schedulers`. Run `uv run --locked pytest -q tests/scheduler/test_days_schedulers.py` to consume them without Rust.
`evidence/phase3_reference.md` records the scheduler inputs, matching decisions,
and preserved DRR activation-order difference.

## Current Days CPU TCP fixtures

`days_tcp.rs` builds seven small Reno/CUBIC TCP flows, runs the actual public CPU
observation API with two workers and Full observations, and records packet
headers, departures, delivery/drop/feedback records, and controller before/after
transitions. Complete Scalar-result equality is a secondary check. The same
wrapper, pinned revision checks, temporary build, retained lock, and provenance
hashes apply:

```sh
uv run --locked python tests/reference/regenerate_days_fifo.py \
  --case tcp --days-root /path/to/days
uv run --locked pytest -q tests/flow/test_days_tcp_reference.py
```

The direct-host cases use MSS 512 bytes, 40-byte immediate ACKs, 8 Gbit/s in
both directions, 100 ns propagation per direction, a 6267-byte transfer with a
123-byte tail, and the controllers' Days initial windows: Reno 1024 bytes and
CUBIC 512 bytes. Two cases explicitly lower the initial threshold to 2048 bytes
to reach congestion avoidance in a small flow. Python compares all four cases'
exact data sequence/size decisions, cumulative ACKs/counts, and link-local
departure/delivery times. Integer-nanosecond serialization permits a one-
femtosecond floating-point tolerance. Global ordering across links is irrelevant.

Three CPU bottleneck cases generate real queue drops and retransmissions.
Reno/CUBIC fast recovery use initial windows of 4096 bytes, a 64 Gbit/s source,
and an 8 Gbit/s FIFO bottleneck with four waiting slots; a smaller Reno transfer
with its ordinary 1024-byte window and one waiting slot produces timeouts.
These cases supply actual CPU feedback to Python controller hooks; they are
controller comparisons, not claims of identical end-to-end loss timing.

Reno windows, thresholds, avoidance credit, and recovery decisions compare
exactly. CUBIC compares floating segment windows with Days nanosegments and
bounds RTT EWMA flooring by less than 8 ns. The observed short no-loss avoidance
curve permits an analytic window bound below 5.12 bytes; recovery window changes
have only lattice/float error. No identity or recovery decision tolerance applies.
A separate counterexample test intentionally omits fresh recovery RTT samples,
as Python transport does under conservative Karn handling, and requires the
CUBIC state comparison to fail. The explicit CPU sample replay does not erase
that transport difference. See `evidence/phase5_reference.md` for exact cases,
rounding derivation, limitations, sensitivity checks, and executed commands.
