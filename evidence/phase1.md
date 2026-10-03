# Phase 1 Python and packages

Recorded on 2026-10-03, based on accepted Phase 0 commit
`0a0cd11`. No `ns/` source, example, or behavioral test changed.

## Versions and provenance

The target is Python 3.14; validation used
[CPython 3.14.8](https://www.python.org/downloads/release/python-3148/) on
macOS arm64 and [uv 0.12.22](https://pypi.org/project/uv/0.12.22/).
Current stable releases were checked against PyPI project pages and their JSON
registry metadata before `uv lock --upgrade`:

| Requirement | Current release |
| --- | --- |
| [SimPy](https://pypi.org/project/simpy/4.1.2/) | 4.1.2 |
| [NetworkX](https://pypi.org/project/networkx/3.7/) | 3.7 |
| [NumPy](https://pypi.org/project/numpy/2.5.3/) | 2.5.3 |
| [PyYAML](https://pypi.org/project/PyYAML/6.0.3/) | 6.0.3 |
| [Matplotlib](https://pypi.org/project/matplotlib/3.11.2/) | 3.11.2 |
| [pytest](https://pypi.org/project/pytest/9.1.1/) | 9.1.1 |
| [Hatchling build requirement](https://pypi.org/project/hatchling/1.32.4/) | >=1.32.4 |

NetworkX's metadata excludes Python 3.14.1. The project mirrors that exclusion
in `Requires-Python`; the upstream
[3.6.1 release notes](https://networkx.org/documentation/stable/release/release_3.6.1.html)
record the blocklist and interpreter issue. NumPy is now an explicit runtime
dependency because the existing MAP/MSP and Pareto traffic generators import it.
pytest is a development dependency, installed by the default locked sync.

Every one of the lockfile's 19 registry packages matched the corresponding
`https://pypi.org/pypi/<name>/json` current release at validation time. The
lockfile includes conditional Windows `colorama`; macOS sync installed 19
packages including the editable project. Build requirements remain separate
from the runtime/development lock, as required by isolated PEP 517 builds.

Both workflows now use the published action references
[checkout v7](https://github.com/actions/checkout/releases/tag/v7.0.1) and
[setup-uv v10.2.0](https://github.com/astral-sh/setup-uv/releases/tag/v10.2.0), with
uv pinned to 0.12.22. uv provisions Python from `.python-version`. Release
publishing keeps the existing token authentication and trigger.

## Validation

| Command | Result |
| --- | --- |
| `uv lock --upgrade` | Passed; refreshed the complete lock, including stale project version metadata. |
| `uv sync --locked` | Passed; replaced the old Python 3.13 environment with a new Python 3.14.8 environment. |
| `uv run pytest -q` | 42 passed in 0.13 seconds. |
| `uv run --locked python scripts/smoke_examples.py` | Passed: basic 0.06s, TCP 0.07s, FatTree 11.30s; each child uses `MPLBACKEND=Agg` and a 90-second timeout. |
| `uv build` | Passed: `ns_py-0.4.5.tar.gz` and `ns_py-0.4.5-py3-none-any.whl`. |
| Isolated wheel install/import below | Passed; imported root package and all 49 submodules from temporary environment `site-packages`. Runtime version and distribution metadata both report 0.4.5; `Requires-Python` is `!=3.14.1,>=3.14`. |
| PyYAML parse of both workflows; `git diff --check` | Passed. |

The isolated install used stdlib `TemporaryDirectory` and `subprocess.run` to
execute the following commands, with the wheel path absolute and working
directory outside the checkout. The temporary environment was then removed.
For replay, allocate `phase1_wheel_dir` with `mktemp -d`:

```shell
uv venv --python 3.14 "$phase1_wheel_dir/venv"
uv pip install --python "$phase1_wheel_dir/venv/bin/python" "$PWD/dist/ns_py-0.4.5-py3-none-any.whl"
"$phase1_wheel_dir/venv/bin/python" -I - <<'PY'
import importlib
import importlib.metadata
import pkgutil
import ns

modules = list(pkgutil.walk_packages(ns.__path__, ns.__name__ + "."))
for module in modules:
    importlib.import_module(module.name)
assert ns.__version__ == importlib.metadata.version("ns.py")
print(f"Imported ns.py {ns.__version__} and {len(modules)} submodules")
print(f"Requires-Python: {importlib.metadata.metadata('ns.py')['Requires-Python']}")
print(f"Module path: {ns.__file__}")
PY
```

CI runs pytest, the same bounded smoke runner, build, and isolated wheel imports.
The curated smoke list excludes real-socket programs. The reported results above
are local. The first hosted run failed during action resolution; see the
correction below. The hosted rerun of the corrected references is pending.
Generated distributions remain ignored and are not committed.

## Published action reference correction

`gh run view 37137236400 --log-failed` showed that the first hosted run failed
before any workflow commands ran: `astral-sh/setup-uv@v10` has no published
major-version alias. The release v10.2.0 exists, but checking its release page
did not verify the shorter tag. Both workflows now use the full v10.2.0 tag.

The following commands verified the actual references on 2026-10-03:

```shell
gh api repos/astral-sh/setup-uv/releases/latest --jq '{tag_name, prerelease, draft, html_url}'
gh api repos/actions/checkout/releases/latest --jq '{tag_name, prerelease, draft, html_url}'
git ls-remote --tags --refs https://github.com/astral-sh/setup-uv.git refs/tags/v10 refs/tags/v10.2.0
git ls-remote --tags --refs https://github.com/actions/checkout.git refs/tags/v7 refs/tags/v7.0.1
```

Both GitHub API releases are stable (`prerelease=false`, `draft=false`).
The setup-uv remote returned only v10.2.0 at
`c18668ad3cf93ea998bef934396af7bb5c839dc7`; it returned no v10 reference.
The checkout remote returned both v7 and v7.0.1 at
`3d3c42e5aac5ba805825da76410c181273ba90b1`, so its existing reference is valid.
YAML parsing and `git diff --check` passed after the correction.

## Size and scope

Simulator executable/code-bearing growth: 0 lines. Simulator explanatory growth:
0 lines. The smoke runner adds 29 code-bearing, 2 explanatory, and 5 blank lines
using Phase 0's physical-line categories. Its only responsibilities are the
three named subprocesses, headless environment, timeout, and failure output.
README and AGENTS instructions now describe the declared test dependency and
`uv lock --upgrade`; the absent `upgrade_packages.py` instruction is removed.
No mechanical configuration/documentation tests were added.

## Acceptance

Candidate `e57d1200cfcf8edb3f9052fba4c24dcc619bb02b` passed independent
6.1-sol/xhigh task review and Astra/medium phase review with no substantive
findings. Integrated-tree pytest (42 passed), smoke examples, and build passed
before publication.
