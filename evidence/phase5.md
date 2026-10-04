# Phase 5 acceptance

Accepted candidate `a1743199a8ba84cb1ac3d9d8eb6a320a47360eb5`. All task reviews,
correction re-reviews, and the final integrated phase gate used fresh internal
gpt-6.1-sol/high agents and passed without remaining substantive findings.

- Reno `4a16861`: [evidence](phase5_reno.md). Byte-counted growth, actual-flight
  loss thresholds, recovery headroom, and consumed feedback context. The small
  byte-ACK bridge preserves the older custom controller callback interface.
  Independent review added 252 closed-form credit/grouping checks.
- CUBIC `5ddbafa` plus `e74cece`: [evidence](phase5_cubic.md). Floating-point Days
  equations, retained beta=0.7, valid time-zero epochs, SRTT, loss maxima and
  fast convergence, and timeout reset. Review found the friendly estimate needed
  its bound before region selection; the reproducer and correction passed fresh
  review (39 focused tests).
- BBR `e30ba9d` plus `1330527`: [evidence](phase5_bbr.md),
  [educational model](../docs/bbr.md). Corrected delivery snapshots, ACK groups,
  round filtering/startup, application limits, pacing, probes, and recovery.
  Review found overlapping ProbeRTT/recovery could lose saved window credit;
  both entry orders now preserve active saved credit. Fresh review passed 77
  focused tests and eight extra overlap combinations, including BDP caps.
- Actual CPU TCP references `80294c7` plus `a174319`:
  [evidence](phase5_reference.md). Seven genuine two-worker Full CPU cases cover
  growth, short tails, avoidance, bottleneck drops, partial/fast recovery, and
  timeout. Four finite network cases align end-to-end. CPU feedback replay
  compares exact decisions and justified numerical bounds. The conservative
  Karn recovery-SRTT difference is an explicit counterexample, not hidden by
  tolerance. Review corrected one misrecorded queue-capacity input; a fresh
  reviewer independently regenerated the entire fixture byte-for-byte and
  passed all 31 combined reference tests. Days remains clean and unchanged.

Final integrated validation: `uv run --locked pytest -q` (**430 passed**) and
`git diff --check`. The same production tree passed
`uv run --locked python scripts/smoke_examples.py` (basic/TCP/FatTree) and
`uv build`; the subsequent reference-only correction changed no production
code or CPU observations. The final phase gate independently ran all 430 tests
and reviewed API integration, transport preservation, evidence, and readability.

These controllers are documented models, not assertions of complete Linux/RFC
conformance. In particular current Days CPU has no BBR, so its educational core
model is accepted through independent invariants and composed flows. No extra
protocols or general cross-simulator framework were introduced. Phases 6 and 7
remain: remaining-component audit, integration, and final readability review.
