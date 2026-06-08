# Agentic TestOps

[![CI](https://github.com/Strangelight-Merser/agentic-testops/actions/workflows/ci.yml/badge.svg)](https://github.com/Strangelight-Merser/agentic-testops/actions/workflows/ci.yml)

Agentic TestOps is a runnable TestOps assistant for Python repositories. It turns a failing test run into a structured engineering report: execute `pytest`, parse failures, classify likely root causes, rerun failing tests, and produce repair-oriented Markdown/JSON output that can be reviewed by a human or passed to a future code-fixing agent.

The project focuses on the "implementation -> verification -> diagnosis -> improvement" loop for Python codebases, using real tools instead of a slide-only demo.

## Why This Project

Modern AI coding workflows often stop at code generation. Real systems need a feedback loop:

1. Run the project's tests with the same command a developer would use.
2. Extract failure signals from noisy tool output.
3. Diagnose whether the issue is behavior, dependency, API contract, data shape, or input validation.
4. Generate a report with evidence and concrete repair advice.
5. Feed the result into the next debugging or patching step.

Agentic TestOps implements the first working slice of that loop, with deterministic behavior that can run in CI without an API key.

## Current Features

- `agentic-testops audit <project>` CLI.
- Runs `python -m pytest --tb=short -q` in the target project.
- Parses pytest failures from JUnit XML first, with text-output parsing as a fallback.
- Optionally reruns only parsed failing node IDs with `--rerun-failures`.
- Converts pytest timeouts into structured reports instead of crashing.
- Preserves user-supplied pytest arguments during focused reruns.
- Diagnoses common Python failure classes:
  - assertion or behavioral regression
  - dependency/import failure
  - API contract mismatch
  - data shape issue
  - input validation boundary bug
  - collection/environment failure
- Writes a professional Markdown report.
- Writes machine-readable JSON for later agent orchestration.
- Generates patch proposal objects with target file, suspected line, action, rationale, confidence, and guardrail tests.
- Generates conservative dry-run unified diff suggestions with `--suggest-fixes` or `--fix-output`.
- Includes two deliberately failing example projects.
- Includes unit tests and GitHub Actions CI.

## Demo Artifacts

- [Project brief](docs/project-brief.md)
- [Buggy calculator report](docs/sample-buggy-calculator-report.md)
- [Buggy calculator dry-run fixes](docs/sample-buggy-calculator-fixes.patch)
- [Task tracker report](docs/sample-task-tracker-report.md)
- [Task tracker dry-run fixes](docs/sample-task-tracker-fixes.patch)
- [Machine-readable task tracker JSON](docs/sample-task-tracker-report.json)

## Quick Start

```bash
python -m pip install -e ".[dev]"
python -m pytest
agentic-testops audit examples/buggy_calculator \
  --rerun-failures \
  --suggest-fixes \
  -o reports/buggy-calculator-report.md \
  --json-output reports/buggy-calculator-report.json \
  --fix-output reports/buggy-calculator-fixes.patch
```

To pass extra pytest arguments, repeat `--pytest-arg`:

```bash
agentic-testops audit . --pytest-arg tests/test_parser.py --pytest-arg=-q
```

The example project should fail because `divide(10, 0)` raises `ZeroDivisionError` while the test expects `ValueError`, and `average([])` also divides by zero. That is intentional: it demonstrates how the tool converts raw pytest output into repair advice.

For a larger demo with multiple failure categories:

```bash
agentic-testops audit examples/task_tracker \
  --rerun-failures \
  --suggest-fixes \
  -o reports/task-tracker-report.md \
  --json-output reports/task-tracker-report.json \
  --fix-output reports/task-tracker-fixes.patch
```

## Example Output

````markdown
# Agentic TestOps Audit Report

- Status: **FAIL**
- Parsed failures: `2`

## Agentic Rerun

- Status: **FAIL**
- Command: `python -m pytest --tb=short -q test_calculator.py::test_divide_rejects_zero ...`

## Diagnosis

### 1. `test_calculator.py::test_divide_rejects_zero`

- Category: `input-validation`
- Summary: The implementation likely misses validation for an invalid or boundary input.

Repair advice:
- Define the intended behavior for the boundary input: reject, clamp, or return a neutral value.
- Guard the operation close to the source of the invalid value.
- Document the behavior in a test so future agents preserve it.

## Patch Proposals

### 1. `test_calculator.py::test_divide_rejects_zero`

- Target: `calculator.py:2`
- Action: Add explicit validation for the failing boundary input before the unsafe operation.

## Dry-Run Fix Suggestions

These diffs are review previews only. They are not applied automatically.

```diff
--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,4 @@
 def divide(a: float, b: float) -> float:
+    if b == 0:
+        raise ValueError("division by zero")
     return a / b
```
````

## Architecture

```text
Target Python project
        |
        v
Pytest runner
        |
        v
JUnit XML + stdout/stderr capture
        |
        v
Failure parser
        |
        v
Rule-based diagnosis agent
        |
        v
Focused failing-test rerun
        |
        v
Patch proposal planner
        |
        v
Markdown / JSON report writer
        |
        v
Human review or future patch-generation agent
```

The current version uses deterministic diagnosis rules so it can run without API keys. The next version can add an optional LLM layer on top of the structured report, but the base system remains reproducible and easy to evaluate.

## Repository Layout

```text
src/agentic_testops/
  cli.py          command-line entry point
  runner.py       pytest execution wrapper
  parser.py       pytest output parser
  diagnoser.py    failure classification and repair advice
  patcher.py      structured patch proposal planner
  fixer.py        conservative dry-run unified diff suggestions
  reporter.py     Markdown and JSON report generation
  models.py       shared dataclasses
examples/
  buggy_calculator/
  task_tracker/
docs/
  project-brief.md
  sample-buggy-calculator-report.md
  sample-buggy-calculator-fixes.patch
  sample-task-tracker-report.md
  sample-task-tracker-fixes.patch
tests/
.github/workflows/
  ci.yml
```

## Two-Week Build Plan Before June 30

### Phase 1: Runnable Core

- Build the CLI, pytest runner, parser, diagnosis rules, reports, and example project.
- Keep the system dependency-light so reviewers can run it quickly.
- Add unit tests for each internal stage.
- Status: implemented.

### Phase 2: Agentic Loop

- Add a `rerun` mode that reruns only failed node IDs.
- Add patch proposal objects in JSON: target file, suspected line, proposed edit summary, and confidence.
- Add a project memory file that records repeated failures and whether prior advice worked.
- Status: rerun and patch proposals implemented; persistent project memory remains planned.

### Phase 3: Demonstration Quality

- Add one larger sample project with three bug types.
- Generate before/after reports and screenshots or terminal transcripts.
- Improve README with badges, design goals, limitations, and evaluation metrics.
- Status: larger sample project, generated reports, and CI are implemented.

### Phase 4: Project Polish

- Publish to GitHub with a clean commit history.
- Add a short demo GIF or terminal recording.
- Write a concise project positioning paragraph:
  - real tool invocation
  - test execution
  - error diagnosis
  - continuous improvement loop
  - extensible automation boundary

## Roadmap

- Optional OpenAI-powered explanation layer.
- GitHub Actions integration that uploads reports as artifacts.
- AST-aware patch suggestion.
- Multi-agent roles: runner, triager, patch planner, verifier.
- Flaky-test detection through repeated runs.
- Coverage-guided test gap analysis.

## Limitations

- The tool suggests repairs but does not edit target code.
- Pytest output parsing is intentionally conservative and may miss exotic plugin formats.
- Diagnosis rules are heuristic; the report is designed to support human review, not replace it.
- Patch proposals are planning hints, not executable code changes.
- Dry-run diffs cover only conservative patterns and should be reviewed before use.

## License

MIT
