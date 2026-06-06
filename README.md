# Agentic TestOps

Agentic TestOps is a small, runnable Agentic AI Infra project for Python repositories. It turns a failing test run into a structured engineering report: execute `pytest`, parse failures, classify likely root causes, and produce repair-oriented Markdown/JSON output that can be reviewed by a human or passed to a future code-fixing agent.

This repository is aimed at **Agentic4Systems Track 03: Agentic AI Infra**. The project focuses on the "implementation -> verification -> diagnosis -> improvement" loop for software systems, using real tools instead of a slide-only demo.

## Why This Project

Modern AI coding workflows often stop at code generation. Real systems need a feedback loop:

1. Run the project's tests with the same command a developer would use.
2. Extract failure signals from noisy tool output.
3. Diagnose whether the issue is behavior, dependency, API contract, data shape, or input validation.
4. Generate a report with evidence and concrete repair advice.
5. Feed the result into the next debugging or patching step.

Agentic TestOps implements the first working slice of that loop.

## Current Features

- `agentic-testops audit <project>` CLI.
- Runs `python -m pytest --tb=short -q` in the target project.
- Parses pytest failure summaries and traceback sections.
- Diagnoses common Python failure classes:
  - assertion or behavioral regression
  - dependency/import failure
  - API contract mismatch
  - data shape issue
  - input validation boundary bug
  - collection/environment failure
- Writes a professional Markdown report.
- Optionally writes machine-readable JSON for later agent orchestration.
- Includes a deliberately failing example project.
- Includes unit tests for parser, diagnoser, and reporter components.

## Quick Start

```bash
python -m pip install -e ".[dev]"
python -m pytest
agentic-testops audit examples/buggy_calculator \
  -o reports/buggy-calculator-report.md \
  --json-output reports/buggy-calculator-report.json
```

To pass extra pytest arguments, repeat `--pytest-arg`:

```bash
agentic-testops audit . --pytest-arg tests/test_parser.py --pytest-arg -q
```

The example project should fail because `divide(10, 0)` raises `ZeroDivisionError` while the test expects `ValueError`, and `average([])` also divides by zero. That is intentional: it demonstrates how the tool converts raw pytest output into repair advice.

## Example Output

```markdown
# Agentic TestOps Audit Report

- Status: **FAIL**
- Parsed failures: `2`

## Diagnosis

### 1. `test_calculator.py::test_divide_rejects_zero`

- Category: `input-validation`
- Summary: The implementation likely misses validation for an invalid or boundary input.

Repair advice:
- Define the intended behavior for the boundary input: reject, clamp, or return a neutral value.
- Guard the operation close to the source of the invalid value.
- Document the behavior in a test so future agents preserve it.
```

## Architecture

```text
Target Python project
        |
        v
Pytest runner
        |
        v
Failure parser
        |
        v
Rule-based diagnosis agent
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
  reporter.py     Markdown and JSON report generation
  models.py       shared dataclasses
examples/
  buggy_calculator/
tests/
```

## Two-Week Build Plan Before June 30

### Phase 1: Runnable Core

- Build the CLI, pytest runner, parser, diagnosis rules, reports, and example project.
- Keep the system dependency-light so reviewers can run it quickly.
- Add unit tests for each internal stage.

### Phase 2: Agentic Loop

- Add a `rerun` mode that reruns only failed node IDs.
- Add patch proposal objects in JSON: target file, suspected line, proposed edit summary, and confidence.
- Add a project memory file that records repeated failures and whether prior advice worked.

### Phase 3: Demonstration Quality

- Add one larger sample project with three bug types.
- Generate before/after reports and screenshots or terminal transcripts.
- Improve README with badges, design goals, limitations, and evaluation metrics.

### Phase 4: Application Polish

- Publish to GitHub with a clean commit history.
- Add a short demo GIF or terminal recording.
- Write a concise application paragraph explaining the Track 03 fit:
  - real tool invocation
  - experiment/test execution
  - error diagnosis
  - continuous improvement loop
  - extensible agent runtime boundary

## Roadmap

- Optional OpenAI-powered explanation layer.
- GitHub Actions integration that uploads reports as artifacts.
- AST-aware patch suggestion.
- Multi-agent roles: runner, triager, patch planner, verifier.
- Flaky-test detection through repeated runs.
- Coverage-guided test gap analysis.

## Limitations

- The first version suggests repairs but does not edit target code.
- Pytest output parsing is intentionally conservative and may miss exotic plugin formats.
- Diagnosis rules are heuristic; the report is designed to support human review, not replace it.

## License

MIT
