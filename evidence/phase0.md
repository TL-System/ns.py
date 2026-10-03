# Phase 0 baseline

Recorded on 2026-10-03 before simulator changes, on branch
`modernize-python314-correctness`. The starting worktree was clean.

- ns.py: `0e9011523a668a8d3d79139cf42cff65643dffa4`.
- Days: `9ff20eac16dcdf752510b05cbcf526684dc05146`.
- Environment: uv `0.12.22`, Python `3.13.16`.
- Plan, full module inventory, and comparison contract:
  [Correctness modernization](../docs/modernization.md).

## Baseline checks

The orchestrator ran these commands against the starting source. Examples used
`MPLBACKEND=Agg` and a 90-second subprocess timeout.

| Command | Result |
| --- | --- |
| `uv sync --locked` | Failed: existing lockfile is stale. No source/lock mutation. |
| `uv sync --frozen` | Passed; installed the existing 15 locked packages. |
| `uv run --frozen --with pytest pytest -q` | 42 passed in 0.14 seconds. |
| `MPLBACKEND=Agg uv run --frozen python examples/basic.py` | Exit 0, approximately 0.07 seconds. |
| `MPLBACKEND=Agg uv run --frozen python examples/tcp.py` | Exit 0, approximately 0.08 seconds. |
| `MPLBACKEND=Agg uv run --frozen python examples/fattree.py` | Exit 0, approximately 11.28 seconds. |

The stale lockfile is a Phase 1 issue. These runs establish a regression baseline,
not algorithm correctness. No actual Days comparison has been run in Phase 0;
the first CPU FIFO comparison is required in Phase 2.

## Source size

Counted all 50 `ns/**/*.py` files, including package initializers. The following
mutually exclusive physical-line categories keep explanatory growth visible:

- Blank: whitespace-only lines, including blanks inside docstrings.
- Explanatory: nonblank module/class/function docstring lines identified with
  Python's AST, plus comment-only lines identified with `tokenize`.
- Code-bearing: remaining nonblank lines, including imports, declarations,
  delimiters, and lines carrying inline comments. This is a size proxy, not a
  count of executable statements or runtime complexity.

Inline comments are reported separately and overlap the code-bearing category.

| Package | Physical | Code-bearing | Explanatory | Blank | Inline comments |
| --- | ---: | ---: | ---: | ---: | ---: |
| Root initializer | 1 | 1 | 0 | 0 | 0 |
| demux | 100 | 48 | 37 | 15 | 0 |
| flow | 681 | 457 | 107 | 117 | 12 |
| packet | 1,865 | 1,292 | 302 | 271 | 14 |
| port | 430 | 232 | 138 | 60 | 2 |
| scheduler | 1,128 | 626 | 302 | 200 | 0 |
| shaper | 332 | 209 | 88 | 35 | 10 |
| switch | 173 | 106 | 50 | 17 | 0 |
| topos | 158 | 90 | 41 | 27 | 0 |
| utils (including generators) | 589 | 307 | 171 | 111 | 4 |
| **Total** | **5,457** | **3,368** | **1,236** | **853** | **42** |

## Inspection findings

The starting code declares Python 3.13 and unbounded runtime requirements;
pytest is not declared as a development dependency. Repository instructions
mention an absent `upgrade_packages.py`. Existing pytest coverage is concentrated
in TCP/BBR and schedulers. In particular, DRR tests expecting automatic quantum
inflation require independent algorithm review.

Current Days CPU imports shared transitions from `executor/src/scalar.rs`.
`executor/src/event.rs` defines its event phases, `time.rs` documents per-service
nanosecond ceiling, and `scalar.rs` documents inclusive simulation stop. Current
`model.rs` supplies FIFO, SP, WFQ, DRR, and WRR; `tcp.rs` supplies Reno/CUBIC.
Virtual Clock and BBR appear in `legacy/`, not that current scheduler/controller
set. RED's current deterministic signaling must be distinguished from ns.py's
random decisions. These are comparison constraints, not requests to copy Days's
architecture or add its extra protocols.

## Acceptance record

Accepted candidate `25aa1ffd08b68db71df69fd6b5d828beda151ed5`: independent
6.1-sol/xhigh task review and Astra/medium phase gate both passed with no
critical, high, or medium findings. No implementation changes were integrated.
The orchestrator re-ran the 42-test baseline on the accepted tree before pushing.
