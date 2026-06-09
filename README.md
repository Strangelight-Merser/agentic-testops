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
  - filesystem boundary issue
  - input validation boundary bug
  - object interface mismatch
  - symbol resolution error
  - collection/environment failure
- Writes a professional Markdown report.
- Writes machine-readable JSON for later agent orchestration.
- Generates patch proposal objects with target file, suspected line, action, rationale, confidence, and guardrail tests.
- Uses import-aware AST lookup to localize API-contract patch targets before falling back to a conservative project scan.
- Generates conservative dry-run unified diff suggestions with `--suggest-fixes` or `--fix-output`.
- Ships as a reusable GitHub Action for CI report generation.
- Includes three deliberately failing example projects.
- Includes unit tests and GitHub Actions CI.

## Demo Artifacts

- [Project brief](docs/project-brief.md)
- [Buggy calculator report](docs/sample-buggy-calculator-report.md)
- [Buggy calculator dry-run fixes](docs/sample-buggy-calculator-fixes.patch)
- [Task tracker report](docs/sample-task-tracker-report.md)
- [Task tracker dry-run fixes](docs/sample-task-tracker-fixes.patch)
- [Machine-readable task tracker JSON](docs/sample-task-tracker-report.json)
- [Service health report](docs/sample-service-health-report.md)
- [Service health dry-run fixes](docs/sample-service-health-fixes.patch)
- [Machine-readable service health JSON](docs/sample-service-health-report.json)
- [GitHub Action usage](docs/github-action.md)

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

## GitHub Action

```yaml
- uses: Strangelight-Merser/agentic-testops@main
  with:
    project: "."
    output: reports/agentic-testops-report.md
    json-output: reports/agentic-testops-report.json
    fix-output: reports/agentic-testops-fixes.patch
    rerun-failures: "true"
    suggest-fixes: "true"
    job-summary: "true"
```

See [GitHub Action usage](docs/github-action.md) for a complete workflow with job summary output and artifact upload.

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

For a service-style demo that covers filesystem, object interface, and symbol resolution failures:

```bash
agentic-testops audit examples/service_health \
  --rerun-failures \
  --suggest-fixes \
  -o reports/service-health-report.md \
  --json-output reports/service-health-report.json \
  --fix-output reports/service-health-fixes.patch
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
  service_health/
  task_tracker/
docs/
  project-brief.md
  sample-buggy-calculator-report.md
  sample-buggy-calculator-fixes.patch
  sample-service-health-report.md
  sample-service-health-fixes.patch
  sample-task-tracker-report.md
  sample-task-tracker-fixes.patch
tests/
.github/workflows/
  ci.yml
action.yml
```

## Project Status

- Runnable CLI and reusable GitHub Action are implemented.
- Markdown, JSON, and dry-run patch artifacts are generated from real pytest runs.
- JUnit XML parsing is preferred, with conservative text parsing as a fallback.
- Focused reruns, timeout reports, and portable command rendering are covered by tests.
- Public examples demonstrate boundary validation, API contract, data shape, and empty-state failures.
- Maintenance files are provided for issues, pull requests, contribution workflow, release checks, and security reporting.

## Maintenance

- [Contributing guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Security policy](SECURITY.md)
- [Release checklist](docs/release-checklist.md)
- [GitHub Action usage](docs/github-action.md)

## Roadmap

- Safer AST-backed edit planning for more Python syntax shapes and call patterns.
- Optional OpenAI-powered explanation layer over deterministic diagnostics.
- GitHub Checks integration that comments summaries on pull requests.
- Historical project memory for repeated failures and flaky-test signals.
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
