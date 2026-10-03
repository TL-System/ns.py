# Current Days CPU FIFO fixture

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
