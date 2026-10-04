# Phase 6 acceptance

Accepted candidate `f91aec8a2a803e35ec358948eae5933ddab01642`. Every task,
correction cycle, and the integrated gate passed fresh internal gpt-6.1-sol/high
review with no remaining medium-or-higher findings.

- RED, token buckets, and marker: `5af3615` plus `15d7094`;
  [evidence](phase6_queues_shapers.md). Resident admission/accounting, RED
  averaging/thresholds, refill/debit, oversized packets, colors, and retained
  ownership pass. Review corrected the documented eligibility versus completion
  envelope for an optional peak serializer. Fresh review checked 57 owned tests
  and 72,000 observation windows across 240 workloads.
- Routing, topology, splitters, monitors, and config: `6b5245b` plus `26f788b`;
  [evidence](phase6_routing_utilities.md). Exact routing/drop behavior, isolated
  branch metadata, failed singleton initialization, YAML key preservation,
  positive recurring sampling intervals, and ACK route collisions are covered.
  Fresh re-review passed 174 related cases and independent YAML key probes.
- Traffic sources, Flow, and mathematical generators: `d1eda31`, `1ce3721`,
  `f91aec8`; [evidence](phase6_sources.md). Exact byte tails and exclusive finish,
  retained streaming arrivals, balanced stationary initialization consistent
  with sampled transitions, and bit-budget Pareto burst eligibility pass.
  Two review cycles exposed decimal and fractional endpoint errors and rounded
  Markov input inconsistency. Final review passed 92 targeted tests, reproduced
  the final regression against its parent, and checked 4,000 burst cases.
- Real-socket proxies: `a16a48a` plus `5bf212a`;
  [evidence](phase6_proxies.md), [model limits](../docs/proxies.md). Actual payload
  lengths, stable TCP/UDP routing, poll-owned delayed delivery, explicit cleanup,
  and retired TCP connection IDs are verified. Fresh review passed 26 related
  tests and additional real-socket lifecycle probes. Late simulated packets
  cannot reopen a connection after EOF, a close marker, or a send error.

The integrated gate independently inspected all component families and pinned
Days source references, and passed 218 focused tests. It confirmed every Phase 6
inventory row has tests or recorded inspection, comments explain the educational
models, and evidence distinguishes CPU comparisons from independent invariants.
No generic simulation or cross-backend framework was added.

Final integrated validation on the accepted production tree:

- `uv run --locked pytest -q`: **648 passed**.
- `uv run --locked python scripts/smoke_examples.py`: basic, TCP, FatTree passed.
- `uv build`: source distribution and wheel built.
- Temporary isolated Python 3.14 environment: wheel installed; root package and
  all 50 submodules imported; package and distribution versions agree (0.4.5).
- `git diff --check` passed; Days checkout remains clean and unchanged.

The local pytest run reports eight pre-existing cleanup warnings for unrelated
read-only temporary model directories. No tests failed; unrelated directories
were preserved. The isolated wheel environment was automatically removed.

Phase 7 remains: composed scenarios, final educational documentation and
inventory closure, source-size review, final package validation, and PR merge.
