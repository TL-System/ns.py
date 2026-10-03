# Phase 2 current Days CPU FIFO comparison

Reference: clean Days checkout at
`9ff20eac16dcdf752510b05cbcf526684dc05146`, read-only at
`/Users/bli/Playground/days`. The helper uses public full CPU observations with
two workers. The entire CPU result also equals the Scalar result; Scalar is a
secondary check, not the source of the recorded departure observations.

The fixture is `tests/reference/days_fifo.json`; retained replay code is
`tests/reference/days_fifo.rs` and `regenerate_days_fifo.py`, with its own small
Cargo dependency lock. Cargo compilation runs in a temporary directory, which
is removed after replay. Neither the Days source nor its lockfile was modified.
Normal pytest reads JSON without Rust or a Days checkout.

## Explicit contract and observed output

One unbounded FIFO egress serializes at 8,000,000,000 bit/s, followed by 100 ns
propagation. Packets are preloaded as arrivals to switch node 1; the source hop
is already complete. All packets use flow/class 0 and route links `[0, 1]`.
There is no loss or random input. Days queue capacity 0 and ns.py `qlimit=None`
permit the same arrivals; this does not assert equal finite-capacity semantics.

| Packet ID | Size (bytes) | Arrival (ns) | CPU departure (ns) | CPU delivery (ns) |
| --- | ---: | ---: | ---: | ---: |
| 0 | 1000 | 0 | 1000 | 1100 |
| 3 | 500 | 0 | 1500 | 1600 |
| 6 | 250 | 500 | 1750 | 1850 |
| 9 | 750 | 1750 | 2500 | 2600 |
| 12 | 125 | 5000 | 5125 | 5225 |

At this rate, serialization is exactly one nanosecond per byte. The first four
packets form one busy interval; packet 9 arrives as packet 6 finishes. Packet 12
starts a new busy interval after an idle period. Actual CPU counters are five
admitted, five departed, five received, 2625 bytes for each, and zero drops.
There are no remaining events or resident packets.

Days processes its inclusive 5225 ns stop time. The Python test fully drains
this finite input and asserts that the last event occurs at that same cutoff.
It compares departure and delivery identities before timing, preserves packet
object identity, verifies final accounting, and compares PacketSink arrival and
wait telemetry. It does not constrain global order between unrelated links.
The absolute 0.000001 ns tolerance is one femtosecond, covering floating-point
accumulation only; a one-nanosecond change is rejected. All Days serialization
intervals here are integral, so no quantization tolerance is needed.

## Executed validation

From `/Users/bli/Playground/ns.py`:

```sh
uv run --locked python tests/reference/regenerate_days_fifo.py \
  --days-root /Users/bli/Playground/days
uv run --locked pytest -q tests/port/test_days_fifo.py
rustfmt --edition 2021 --check tests/reference/days_fifo.rs
git -C /Users/bli/Playground/days status --short
```

Replay printed `Recorded actual Days CPU FIFO observations in
/Users/bli/Playground/ns.py/tests/reference/days_fifo.json`. The recorded JSON
contains the table above, full admission/delivery records, counters, reference
revision, helper/lock SHA-256 hashes, replay command, and compiler version.
The targeted Python suite passed: **2 passed**. Rust formatting passed and the
Days status output was empty. Build artifacts remained outside both repositories.

The Python comparison also ran through two controlled fixture mutations,
restoring the actual CPU JSON in a `finally` block after each batch. These are
harness-sensitivity checks, not evidence of a pre-existing FIFO algorithm bug:

- Swapped the first two recorded departures and ran
  `uv run --locked pytest -q
  tests/port/test_days_fifo.py::test_fifo_port_and_wire_match_days_cpu_observations`.
  Exit 1: actual identities `[0, 3, 6, 9, 12]` differed from
  `[3, 0, 6, 9, 12]` at index 0.
- Increased the first recorded departure from 1000 ns to 1001 ns and ran the
  same command. Exit 1: obtained 1000.0 ns versus `1001 +/- 0.000001` ns.
- Restored the JSON and reran the targeted suite: **2 passed**.

No production simulator changes were needed for this comparison. This evidence
covers the FIFO reference task only; the phase gate separately validates the
other Phase 2 components and the integrated tree.
