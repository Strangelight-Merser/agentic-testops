# Changelog

All notable changes to Agentic TestOps are documented here.

## Unreleased

### Added

- Reusable GitHub Action with Markdown, JSON, patch artifact, and job summary output.
- JUnit XML-first pytest failure parsing with text-output fallback.
- Conservative dry-run fix suggestions that emit reviewable unified diffs.
- Multi-line function signature support for conservative API-contract fix suggestions.
- Import-aware API-contract target localization for patch proposals.
- Diagnosis categories for filesystem boundary, object interface, and symbol resolution failures.
- Service health example project and sample reports covering the newer diagnosis categories.
- Demo walkthrough that connects the service health failures to report, JSON, and patch proposal artifacts.
- Focused reruns for parsed failing pytest node IDs.
- Timeout handling that returns a structured report instead of crashing.
- Public sample projects and generated reports.
- Open-source maintenance files for contributions, issues, pull requests, security reporting, and releases.

### Changed

- Reports use portable `python -m pytest ...` command rendering instead of machine-specific Python paths.
- Public reports use a safe display path for absolute project targets.
- Public project wording is general-purpose and not tied to external application tracks.
- CI now validates the supported Python version range from 3.9 through 3.12.
- GitHub workflow examples use current official action major versions for the Node 24 runtime.

### Notes

- Dry-run diffs are intentionally conservative and should be reviewed before use.
