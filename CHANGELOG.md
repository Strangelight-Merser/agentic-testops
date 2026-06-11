# Changelog

All notable changes to Agentic TestOps are documented here.

## Unreleased

### Added

- Closed-loop fix verification with `--apply-and-verify`: dry-run fix suggestions are applied to a temporary copy of the project, the guardrail tests and the full suite are rerun there, and the audit report records a `fix-confirmed`, `fix-ineffective`, `fix-regressed`, or `patch-failed` verdict with new-failure detection against the baseline run. Parsed node IDs that carry repository or absolute path prefixes are localized to the copied tree before the rerun. The audited project is never modified.

## 0.2.0 - 2026-06-10

### Added

- PyPI release workflow: publishing a GitHub Release builds sdist/wheel, validates metadata with twine, and uploads through PyPI trusted publishing.
- Real-world evaluation harness (`scripts/evaluate_real_world.py`) that replays historical upstream bug fixes (more-itertools, tabulate, boltons) with a revert-source-keep-tests procedure.
- Evaluation report (`docs/real-world-evaluation.md`) documenting parsing robustness, localization hits against upstream fix ground truth, and the assertion-localization blind spot.
- Simplified Chinese README (`README.zh-CN.md`) with cross-links between both languages, kept in sync by a hygiene test.
- Optional LLM analysis layer (`--llm-explain`, `--llm-provider`, `--llm-model`, `--llm-base-url`): structured failure evidence is sent to the Anthropic API or any OpenAI-compatible endpoint (OpenAI, DeepSeek, Qwen, Zhipu, Moonshot, local Ollama/vLLM) via the standard library (no new dependencies) and rendered as an advisory section; missing keys or request failures degrade gracefully without affecting the audit.
- Import-graph localization for assertion failures whose traceback never leaves test code: the failing test module's imports and calls are resolved with AST (including one level of package re-exports) to point patch targets at implementation definitions. Verified against the real-world evaluation: the tabulate and more-itertools assertion cases moved from test-helper misses to upstream-fix hits.

## 0.1.0 - 2026-06-10

### Added

- Flaky failure detection with `--detect-flaky N`: failing tests are rerun in isolation and classified as `flaky` or `consistent` in the Markdown report, JSON output, and repair guidance.
- Deterministic shared-state flaky example project (`examples/flaky_pipeline`) with sample report artifacts and a CI smoke test asserting both verdicts.
- Ruff linting and strict mypy type checking, enforced by a dedicated CI lint job.
- Reusable GitHub Action with Markdown, JSON, patch artifact, and job summary output.
- JUnit XML-first pytest failure parsing with text-output fallback.
- Conservative dry-run fix suggestions that emit reviewable unified diffs.
- Multi-line function signature support for conservative API-contract fix suggestions.
- Import-aware API-contract target localization for patch proposals.
- Diagnosis categories for filesystem boundary, object interface, and symbol resolution failures.
- Service health example project and sample reports covering the newer diagnosis categories.
- Demo walkthrough that connects the service health failures to report, JSON, and patch proposal artifacts.
- Dry-run fix suggestions for the service health demo's filesystem boundary, object interface, and symbol resolution failures.
- Focused reruns for parsed failing pytest node IDs.
- Timeout handling that returns a structured report instead of crashing.
- Public sample projects and generated reports.
- Open-source maintenance files for contributions, issues, pull requests, security reporting, and releases.

### Changed

- Reports use portable `python -m pytest ...` command rendering instead of machine-specific Python paths.
- Public reports use a safe display path for absolute project targets.
- Public project wording is general-purpose and not tied to external application tracks.
- Supported Python range is now 3.10 through 3.13; 3.9 was dropped after reaching end of life.
- GitHub workflow examples use current official action major versions for the Node 24 runtime.

### Notes

- Dry-run diffs are intentionally conservative and should be reviewed before use.
