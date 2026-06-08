# Contributing

Thanks for helping improve Agentic TestOps. The project is intentionally small and deterministic: changes should make Python test diagnosis more reliable, easier to adopt, or easier to review.

## Development Setup

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

Run the example audit:

```bash
agentic-testops audit examples/buggy_calculator \
  --rerun-failures \
  --suggest-fixes \
  -o reports/buggy-calculator-report.md \
  --json-output reports/buggy-calculator-report.json \
  --fix-output reports/buggy-calculator-fixes.patch
```

The example project is expected to fail. The audit command should still generate Markdown, JSON, and patch preview artifacts.

## Contribution Guidelines

- Prefer deterministic rules and structured pytest data before adding heuristic text parsing.
- Do not mutate a target project unless the command name and documentation make that behavior explicit.
- Keep dry-run fix suggestions conservative and reviewable.
- Add tests for parser behavior, CLI behavior, generated reports, and any new diagnosis category.
- Public docs should describe Agentic TestOps as a general TestOps assistant and avoid event- or track-specific positioning.

## Pull Request Checklist

- [ ] `python -m pytest -q` passes.
- [ ] Public sample reports are refreshed if user-visible output changed.
- [ ] New CLI flags are documented in `README.md`.
- [ ] GitHub Action inputs or outputs are documented in `docs/github-action.md`.
- [ ] No local absolute paths, credentials, or machine-specific values are committed.
