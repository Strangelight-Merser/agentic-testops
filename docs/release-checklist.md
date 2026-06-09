# Release Checklist

Use this checklist before tagging a public release.

1. Run tests:

   ```bash
   python -m pytest -q
   ```

2. Regenerate sample artifacts:

   ```bash
   agentic-testops audit examples/buggy_calculator \
     --rerun-failures \
     --suggest-fixes \
     -o docs/sample-buggy-calculator-report.md \
     --json-output docs/sample-buggy-calculator-report.json \
     --fix-output docs/sample-buggy-calculator-fixes.patch

   agentic-testops audit examples/task_tracker \
     --rerun-failures \
     --suggest-fixes \
     -o docs/sample-task-tracker-report.md \
     --json-output docs/sample-task-tracker-report.json \
     --fix-output docs/sample-task-tracker-fixes.patch

   agentic-testops audit examples/service_health \
     --rerun-failures \
     --suggest-fixes \
     -o docs/sample-service-health-report.md \
     --json-output docs/sample-service-health-report.json \
     --fix-output docs/sample-service-health-fixes.patch
   ```

3. Verify generated patches apply to temporary copies of the example projects.
4. Check public artifacts for machine-specific paths or secrets.
5. Update `CHANGELOG.md`.
6. Create a Git tag and GitHub release.
7. Confirm the GitHub Action usage example works against the new tag.
