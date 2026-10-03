# Phase 3 progress and pending WFQ decision

The independent portion at `d96f2c97cb2fb7230cb9430c2c1e25d84c850700`
has passed task reviews and an Astra/medium interim integration review. This is
not full Phase 3 acceptance and does not authorize starting Phase 4.

## Reviewed tasks

- Strict priority: `5db0fad693e92690e5928357ab0e2b87c38604c1`;
  [evidence](phase3_sp.md).
- Virtual Clock: `1ac673c9f9b25572fc2eecb0c2396adbd62e26c1`;
  [evidence](phase3_virtual_clock.md).
- DRR: `37e6a14a97fcb8ee104f46763743b82ea18aa8e3` plus the reviewed
  None-class correction `02f48aed951ad4970a20e6614da012753db12a9e`;
  [evidence](phase3_drr.md). Fresh review passed after the correction.
- Actual Days CPU scheduler observations:
  `8ad3e41429f4283c278927dc4f5fee630951305e`;
  [evidence and model counterexamples](phase3_reference.md).
- Shared-buffer identity and class-aware monitoring:
  `d96f2c97cb2fb7230cb9430c2c1e25d84c850700`;
  [evidence](phase3_composition.md). Its independent review also revalidated the
  integrated scheduler callbacks.

All completed task reviews used fresh 6.1-sol/xhigh agents and found no remaining
critical, high, or medium findings. Integrated validation passed:
`uv run --locked pytest -q --ignore=tests/scheduler/test_wfq.py` (216 tests),
`uv run --locked python scripts/smoke_examples.py` (basic, TCP, FatTree),
`uv build`, and each existing two-level SP/DRR/WFQ example (18 deliveries and
fully released retained storage). The helper `ns/utils/retained_store.py` is the
only new runtime module; it centralizes exact-object release for existing
composition callbacks, rather than adding a scheduling framework.

## Required decision

Current Days WFQ uses queued plus in-service packets to decide which classes
advance virtual time. Textbook WFQ uses a fluid GPS reference; these models can
choose different packets even with exact arithmetic. The actual CPU
counterexample is recorded in the reference evidence. The orchestrator requested
user direction between textbook WFQ (recommended for educational correctness)
and matching Days with an explicitly documented approximation. No answer has
been assumed.

The WFQ implementer preserved `tests/scheduler/test_wfq.py` as uncommitted work in
progress: its initial 12 failed / 2 passed result captures first-tag, idle,
fairness, telemetry, and input defects. Those intentionally red tests were not
weakened or silently marked passing. The kernel remains unchanged; only its
shared-buffer callback plumbing was repaired with the other schedulers.

After the user chooses, resume the original WFQ implementer, add the appropriate
Python/Days comparisons, obtain fresh task review, run the complete suite with
no WFQ exclusion, and complete the final Astra phase gate. Phases 4 through 7
remain unstarted. Preserve this paused work during cleanup.
