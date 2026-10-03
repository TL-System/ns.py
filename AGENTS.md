# Repository Guidelines

## Project Structure & Module Organization
The `ns/` package contains the simulator core, grouped by concern (`flow`, `packet`, `port`, `scheduler`, `switch`, `shaper`, `demux`, `topos`). Mirror that layout when adding primitives so imports stay predictable. Keep runnable scenarios in `examples/` so they double as integration smoke tests (e.g., `uv run python examples/basic.py`). Architecture notes, diagrams, and references belong in `docs/`. Treat `build/` as disposable packaging output and keep generated wheels out of commits.

## Build, Test, and Development Commands
Target Python 3.14+ (see `.python-version`), excluding 3.14.1 to match NetworkX's requirements. Use `uv sync --locked` to create/update `.venv` and install the project in editable mode, including pytest. Use `uv lock --upgrade` followed by `uv sync --locked` when dependencies need refreshing; review the lockfile diff. `uv build` must pass before publishing so metadata and package data match `ns/__init__.py`. Run `uv run pytest -q` for regressions and add new suites under `tests/<module>/test_<feature>.py`. Run `uv run --locked python scripts/smoke_examples.py` for finite, headless basic/TCP/FatTree checks with a 90-second timeout per example. Replay individual scenarios with `MPLBACKEND=Agg uv run --locked python examples/tcp.py` or `examples/fattree.py`. Real-socket examples require an explicit local setup and are outside the CI smoke list.

## Coding Style & Naming Conventions
Stay within PEP 8: four-space indentation, ~88-character lines, `snake_case` functions, and `PascalCase` classes (see `ns/flow/bbr.py`). Place new schedulers under `ns/scheduler`, new traffic sources under `ns/packet`, and keep modules single-purpose. Type hints are encouraged on public methods, and each SimPy process should include a short docstring explaining timing assumptions. When editing rate/size math, include a concise comment explaining byte/bit conversions because downstream components rely on those invariants.

## Testing Guidelines
Pytest is the canonical harness; mark stochastic or long-running cases with `@pytest.mark.slow` to keep `uv run pytest -q` fast. Cover control-flow inside SimPy processes by asserting queue order, delay counters, or monitor telemetry, and ensure every new branch yields at least once. Complement unit tests with manual example runs and capture the CLI parameters you used so reviewers can replay them quickly.

## Commit & Pull Request Guidelines
Keep commits short and imperative, mirroring existing history (`Fixed duplicate arrival times...`, `Changed the time...`). Reference issues with `Closes #123` or `(#123)` trailers. Pull requests should describe the topology or algorithm change, list the exact test or example commands used, and link any docs that moved. When behavior changes visibly (e.g., queue occupancy charts), drop screenshots or sink statistics in the description. Keep each PR focused on one theme so reviews stay tractable.
