# Phase 7: educational documentation and readability

Input is accepted Phase 6 `aa73e17`, following reviewed production candidate
`f91aec8a2a803e35ec358948eae5933ddab01642`. The original baseline is
`0e9011523a668a8d3d79139cf42cff65643dffa4`. This task changes README,
`docs/modernization.md`, new `docs/model_notes.md`, and production comments or
docstrings only. No algorithm, constructor, dependency, or public import changes
are part of this task. The coordinator records the exact review snapshot and
final integrated gate separately; no task-local check implies phase acceptance.

## Inventory and teaching documentation

Every production module has an explicit closed row in the
[component inventory](../docs/modernization.md#component-inventory), including
all eleven package initializers and the added retained-store helper. Each
algorithm row links accepted task evidence and observable tests; unsupported CPU
counterparts are marked as gaps rather than equating passing Python tests with
CPU parity. Phase acceptance records 0–6 were read alongside their family
implementation/reference evidence.

[Model notes](../docs/model_notes.md) summarize the units, waiting/service/retained
occupancy distinction, floating-point and equal-time limits, chosen Days
packet-active WFQ recurrence, textbook DRR differences, random RED versus
counter-signaled CPU RED, independently tested educational BBR, and transport,
shaper, traffic-source, and socket behavior changes. They link detailed TCP/BBR/
proxy contracts and reference evidence instead of duplicating their full state
machines. The README now points students to these boundaries and the finite
composition example before they interpret plots as full protocol behavior.

The production review inspected module/class/function documentation and all
comment tokens against the relevant process, state, tests, and accepted evidence.
Corrections are local teaching improvements:

- `switch/switch.py`: include SP among supported disciplines; explain resident
  capacity and retained-port ownership; describe class mapping for every variant.
- `utils/taggedstore.py`: describe heap entries accurately; heap storage is not
  a globally sorted list.
- `topos/utils.py`: remove the obsolete commented all-simple-path alternative;
  explain shortest-path selection, GraphML behavior, and reverse ACK ports.
- `scheduler/monitor.py`: replace the stale count of three callbacks with the
  actual measurement interface.
- `packet/sink.py`: explain that recorded waits include end-to-end service and
  propagation, rather than only queue waiting.
- `packet/packet.py`: replace a commented-out `sent_time` assignment with the
  attempt-sampler ownership rule; include TrTCM in the color-field comment.

README corrections remove the fixed-size proxy claim, transient “TCP rewrite”
wording, `VirtualClockQServer` typo, reversed RED acronym, stale test count, and
incorrect UDP listener port. The component tutorial now describes Python
cooperative generators in simulated time; the previous prose incorrectly called
ordinary processes real-time and equated Python `yield` with an OS system call.
Its snippets match current FIFO timing and class-based composition, and it
explains numeric stop-time exclusion and idle wakeup versus heap selection.

No substantive production bug was found in this final documentation audit. No
executable simplification was needed: accounting, one oldest TCP timer, small
local wakeups, and exact-object release state already have invariant tests and
teach their purpose. Direct `put()`/`out` composition and small SimPy loops remain.
No new engine, scheduler framework, configuration framework, or cross-simulator
framework was introduced. Existing detailed comments were preserved where they
explain units, state transitions, recovery, callback timing, and model limits.

## Import and public API inspection

A locked Python 3.14 run imported `ns` and every module found by
`pkgutil.walk_packages(ns.__path__, 'ns.')`: **51 modules**, consisting of the root
and 50 submodules. Runtime `ns.__version__`, installed editable distribution
metadata, and `pyproject.toml` all report **0.4.5**. This is source-tree import
validation; the coordinator performs the separate isolated wheel installation.

All eleven initializers were inspected individually: root, demux, flow, packet,
port, scheduler, shaper, switch, topos, utils, and utils/generators. The root has
only `__version__ = "0.4.5"`; the other ten are empty package markers, so no eager
imports, implicit exports, or initialization state need algorithm tests. Existing
module-qualified imports remain the public usage convention, such as
`from ns.scheduler.wfq import WFQServer`. `utils/retained_store.py` is a small
internal composition helper, not a new package-level export.

For every production file, AST comparison against `aa73e17` removed only initial
module/class/function docstring expressions and ignored locations via `ast.dump`.
The executable AST is identical in all 51 modules. Exactly six production files
have textual edits, all listed above. Existing public classes/functions and
constructor signatures therefore remain identical to accepted Phase 6. Necessary
behavior changes from earlier phases, including CUBIC's retained-fraction beta
meaning and source/proxy timing rules, remain visible in the model notes.

Reproduce source imports independently:

```sh
uv run --locked python - <<'PY'
import importlib
import importlib.metadata
import pkgutil
import ns

modules = list(pkgutil.walk_packages(ns.__path__, ns.__name__ + '.'))
for module in modules:
    importlib.import_module(module.name)
print(len(modules) + 1, ns.__version__, importlib.metadata.version('ns.py'))
PY
```

## Whole-production source measurement

The measurement includes every `ns/**/*.py` file, even empty initializers and
new internal modules. Blank wins over all other categories. Explanatory means
nonblank AST module/class/function docstring lines plus tokenize comment-only
lines. All remaining nonblank lines are code-bearing, including declarations,
imports, delimiters, and inline comments. These are physical source categories,
not executable-statement or complexity measurements. Inline comments overlap
code-bearing lines and are shown separately.

The baseline reproduces Phase 0 exactly: **50 modules, 5457 physical / 3368
code-bearing / 1236 explanatory / 853 blank**, with 42 inline comments. Final
production has **51 modules, 5650 / 3484 / 1417 / 749**, with 36 inline comments.
Net growth is **193 physical (+3.54%), 116 code-bearing (+3.44%), 181 explanatory
(+14.64%), and -104 blank** lines. The sole added runtime module is the 21-line
`utils/retained_store.py`; it is included in utils below.

| Package | Baseline P / C / E / B | Final P / C / E / B | Delta P / C / E / B | Inline baseline / final |
| --- | ---: | ---: | ---: | ---: |
| root | 1 / 1 / 0 / 0 | 1 / 1 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 |
| demux | 100 / 48 / 37 / 15 | 137 / 75 / 47 / 15 | 37 / 27 / 10 / 0 | 0 / 0 |
| flow | 681 / 457 / 107 / 117 | 779 / 521 / 150 / 108 | 98 / 64 / 43 / -9 | 12 / 12 |
| packet | 1865 / 1292 / 302 / 271 | 1726 / 1215 / 326 / 185 | -139 / -77 / 24 / -86 | 14 / 12 |
| port | 430 / 232 / 138 / 60 | 394 / 214 / 125 / 55 | -36 / -18 / -13 / -5 | 2 / 1 |
| scheduler | 1128 / 626 / 302 / 200 | 1192 / 654 / 351 / 187 | 64 / 28 / 49 / -13 | 0 / 0 |
| shaper | 332 / 209 / 88 / 35 | 369 / 224 / 100 / 45 | 37 / 15 / 12 / 10 | 10 / 8 |
| switch | 173 / 106 / 50 / 17 | 176 / 106 / 52 / 18 | 3 / 0 / 2 / 1 | 0 / 0 |
| topos | 158 / 90 / 41 / 27 | 164 / 94 / 42 / 28 | 6 / 4 / 1 / 1 | 0 / 0 |
| utils, including generators | 589 / 307 / 171 / 111 | 712 / 380 / 224 / 108 | 123 / 73 / 53 / -3 | 4 / 3 |
| **Total** | **5457 / 3368 / 1236 / 853** | **5650 / 3484 / 1417 / 749** | **193 / 116 / 181 / -104** | **42 / 36** |

Compared with accepted Phase 6 `aa73e17` (5647 / 3484 / 1415 / 748), this final
pass adds **3 physical, 0 code-bearing, 2 explanatory, and 1 blank** line. Test,
example, and Markdown growth is deliberately excluded from production totals.
Phase 7 composition adds no runtime module or executable production change.

Reproduce the exact categories and totals from repository history and the
current worktree; use the same `count` function grouped by package for the table:

```sh
uv run --locked python - <<'PY'
import ast
from collections import Counter
import io
from pathlib import Path
import subprocess
import tokenize


def count(source):
    lines = source.splitlines()
    explanatory = set()
    kinds = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, kinds) and ast.get_docstring(node):
            doc = node.body[0]
            explanatory.update(range(doc.lineno, doc.end_lineno + 1))
    result = Counter(physical=len(lines), inline=0)
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            prefix = lines[token.start[0] - 1][:token.start[1]]
            if prefix.strip():
                result['inline'] += 1
            else:
                explanatory.add(token.start[0])
    for number, line in enumerate(lines, 1):
        category = ('blank' if not line.strip() else
                    'explanatory' if number in explanatory else 'code')
        result[category] += 1
    return result


for revision in ['0e9011523a668a8d3d79139cf42cff65643dffa4', 'aa73e17', None]:
    if revision is None:
        sources = [p.read_text() for p in sorted(Path('ns').rglob('*.py'))]
    else:
        paths = subprocess.check_output(
            ['git', 'ls-tree', '-r', '--name-only', revision, 'ns'], text=True
        ).splitlines()
        sources = [subprocess.check_output(
            ['git', 'show', f'{revision}:{p}'], text=True
        ) for p in paths if p.endswith('.py')]
    total = Counter()
    for source in sources:
        total.update(count(source))
    print(revision or 'worktree', len(sources), dict(total))
PY
```

## Validation scope

`git diff --check` passes. No mechanical documentation tests were added. Imports,
AST preservation, reproduced physical counts, evidence/test path inspection, and
reading the edited prose establish this task's scope. The coordinator's final
regression, CPU fixture consumption, four-example smoke runner, build, and
isolated wheel checks establish the final integrated result.

The coordinator also reported bounded headless runs of `bbr.py`, `drr_jumbo.py`,
`fair_packet_switch.py`, `mm1.py`, `overloaded_switch.py`, `static_priority.py`,
`virtual_clock.py`, `wfq.py`, `drr.py`, `two_level_drr.py`, `two_level_wfq.py`, and
`two_level_sp.py`: all exit 0. These used a locked uv Python subprocess harness,
`MPLBACKEND=Agg`, the repository working directory, and a 90-second timeout per
example. The independent composition task records its teaching example and
mixed-size hierarchy, congestion, FatTree, and TCP-loss observations in
[composition evidence](phase7_composition.md). These are reported integration
observations rather than new algorithm repairs by this documentation task.
