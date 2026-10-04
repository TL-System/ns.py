# Phase 4 acceptance

Accepted candidate `c658fbfac31726db94c34c2e650fb9d77d7262c3` after fresh
internal gpt-6.1-sol/high task reviews and the final phase gate passed.

- Classic transport: initial `e3d604d`, recovery correction `c8296f1`;
  [task evidence](phase4_tcp_sender.md). Fresh final task review passed 50
  focused tests and reproduced all four review regressions on the old source.
- Paced BBR transport: initial `9466d4f`, recovery correction `8180892`,
  zero-RTT correction `c658fbf`; [task evidence](phase4_bbr_sender.md).
  Fresh recovery and zero-RTT reviews passed, including 100 additional loss and
  reordering traces and the recorded red/green cases.
- Receiver and shared integration: `2572805`;
  [task evidence](phase4_receiver.md). Review passed 24 focused cases and an
  independent received-byte oracle over 25,000 interval arrivals.

The first sender reviews found unbounded synchronous partial-recovery recursion;
small local zero-time yields now break the forwarding stack and suppress stale
requests. The first phase gate found that BBR ignored valid zero RTT samples;
the estimator now accepts them independently of the delivery-rate division guard.
Each correction returned to its implementer and received fresh review. The final
phase gate passed 113 focused transport tests with no substantive findings.

Integrated validation on the accepted candidate: `uv run --locked pytest -q`
(**340 passed**), `uv run --locked python scripts/smoke_examples.py` (basic,
TCP, FatTree), `uv build` (wheel and sdist), and `git diff --check` all passed.
Both senders now handle integral MSS/tail segmentation, valid cumulative ACKs,
unique flight bytes, one oldest-range timer, partial recovery, exclusive new-data
deadlines, outstanding-data drain, and original latency timestamps. The receiver
keeps simple merged ranges and distinguishes physical arrivals from unique
contiguous delivery through a read-only property.

See the [timing contract](../docs/tcp_timing.md) for the intentional conservative
Karn and SimPy equal-time differences from Days. Congestion-window formulas,
full BBR sampling/variant work, and actual CPU TCP comparison remain Phase 5;
passing transport tests does not claim those later audits are complete.
