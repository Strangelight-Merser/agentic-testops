# Real-World Evaluation

This document evaluates Agentic TestOps against failures from real open-source
projects, not the tool's own demo examples. The goal is an honest answer to one
question: how does the diagnosis pipeline behave on pytest output it was never
tuned for?

## Methodology

The evaluation replays historical bugs with a SWE-bench style
"revert source, keep tests" procedure, implemented in
[`scripts/evaluate_real_world.py`](../scripts/evaluate_real_world.py):

1. Check out a real upstream bug-fix commit that touched both implementation
   code and tests.
2. Restore only the implementation files from the fix commit's parent, keeping
   the regression tests introduced or updated by the fix.
3. The working tree now reproduces the historical bug exactly as the upstream
   maintainers encountered it.
4. Run `agentic-testops audit` on that tree and compare the report against the
   ground truth: the files and lines the real fix actually changed.

The replayed failures were written by other maintainers and were never used to
design this tool's diagnosis rules. One additional case uses an unmodified
checkout of boltons, whose `conftest.py` is incompatible with modern pytest --
a realistic collection/environment failure.

To reproduce:

```bash
python scripts/evaluate_real_world.py --workdir /tmp/ato-eval --output reports/real-world
```

## Cases and Results

| Case | Upstream fix | Failures parsed | Category assigned | Localization vs. ground truth |
| --- | --- | --- | --- | --- |
| more-itertools `numeric_range.__reversed__` IndexError | [edb3346](https://github.com/more-itertools/more-itertools/commit/edb3346) | 1/1 | `data-shape` | Correct file (`more_itertools/more.py`); pointed at the raise site in `_get_by_index`, one frame below the fixed `__reversed__` method |
| more-itertools `repeat` with iterator args | [be5793a](https://github.com/more-itertools/more-itertools/commit/be5793a) | 2/2 | `input-validation`, `behavioral-regression` | 1 of 2 correct: the ValueError failure landed inside the fixed `partial_product` validation; the assertion failure was blamed on the test file |
| more-itertools `nth_combination_with_replacement` wrong exception | [06f3181](https://github.com/more-itertools/more-itertools/commit/06f3181) | 2/2 | `input-validation` | Both failures pointed at `more.py:4277`, inside the exact hunk the upstream fix changed |
| tabulate asciidoc trailing whitespace | [3aa568c](https://github.com/astanin/python-tabulate/commit/3aa568c) | 3/3 | `behavioral-regression` | Miss: all three blamed the shared assert helper `test/common.py:10`; the real fix was in `tabulate/__init__.py` |
| boltons with modern pytest (unmodified) | n/a | 0 (collection crash) | `collection-or-environment` | Correctly reported as an environment failure instead of crashing or inventing per-test diagnoses |

Sample artifacts are kept in [`docs/real-world/`](real-world/).

## What Held Up

- **Parsing is robust on real output.** All 8 runtime failures across a
  715-test suite (with `pytest-subtests` noise) and a second project were
  parsed with correct node IDs and error types. The boltons collection crash
  produced a structured report instead of a stack trace.
- **Exception-bearing failures localize well.** When the failure carries a
  raised exception (IndexError, ValueError), the deepest implementation frame
  is in or adjacent to the region the upstream fix actually changed (3 of 4
  such failures, with the fourth in the correct file).
- **Wrong-exception bugs map to the right category.** The
  `nth_combination_with_replacement` case -- a function raising `ValueError`
  where `IndexError` was expected -- was classified `input-validation` with
  the patch target inside the real fix hunk.

## What Did Not Hold Up

- **Pure output-comparison assertions defeat frame-based localization.** When
  a test asserts `expected == actual` on a computed string (tabulate), the
  traceback contains only test frames, so the "deepest project frame"
  heuristic blames the shared assert helper. The category is still correct,
  but the patch target is useless. A fix would need import-graph analysis from
  the failing test module to candidate implementation modules.
- **Multi-bug commits dilute attribution.** The `repeat` case reverted a
  commit containing two distinct fixes; the assertion-style failure was
  attributed to the test file rather than the implementation.
- **Category granularity is debatable on real bugs.** The IndexError
  regression was labeled `data-shape`; `behavioral-regression` would arguably
  describe it better. Categories assigned to real failures cluster heavily in
  three buckets, suggesting the finer-grained categories mostly fire on
  curated examples.

## Honest Summary

On real repositories the pipeline is reliable as a *parser and triage layer*:
it survives real pytest output, classifies failures into sensible coarse
buckets, and localizes exception-bearing failures usefully. It is weak as a
*repair planner* for assertion-style failures, which are the most common kind
in mature projects. That boundary is now documented, tested against real
ground truth, and is the primary input for the roadmap (import-graph
localization, then an optional LLM layer over the structured report).
