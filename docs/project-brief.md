# Agentic TestOps Project Brief

## Project

**Agentic TestOps** is a TestOps assistant prototype for Python projects. It automates a concrete feedback loop:

1. Execute the target project's tests.
2. Parse noisy failure output into structured failure objects.
3. Diagnose likely root causes.
4. Rerun only failing node IDs to confirm reproducibility.
5. Generate patch proposal objects and human-readable reports.

## Technical Focus

The project treats testing as an active automation primitive rather than a passive CI afterthought. The system has explicit tool use, task decomposition, verification steps, structured intermediate state, and report artifacts that can be consumed by future patching or orchestration agents.

## Current Demo

The repository includes two intentionally failing Python projects:

- `examples/buggy_calculator`: boundary input validation failures.
- `examples/task_tracker`: API contract, data shape, and empty-state failures.

The CLI produces Markdown and JSON reports. JSON output is designed to be machine-readable so another agent can consume the failure, diagnosis, rerun result, and patch proposal objects.

## Evaluation Signals

- Unit tests validate parser, diagnosis, patch proposal, and report behavior.
- GitHub Actions runs the tool on every push.
- Sample reports are generated from real pytest output rather than handwritten fixtures.
- The design avoids requiring an API key for the base demo, which improves reproducibility.

## Next Extensions

- AST-aware line localization for patch proposals.
- Optional LLM explanation layer over deterministic diagnostics.
- GitHub Checks integration that comments summaries on pull requests.
- Multi-agent runtime split: runner, triager, patch planner, verifier.
- Flaky-test detection by repeated reruns and historical failure memory.
