# GitHub Action Usage

Use Agentic TestOps in a workflow to generate a Markdown report, JSON report, and optional dry-run patch preview from pytest failures.

```yaml
name: Agentic TestOps

on:
  pull_request:
  push:

jobs:
  testops:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"

      - name: Install project test dependencies
        run: python -m pip install -e ".[dev]"

      - name: Run Agentic TestOps
        uses: Strangelight-Merser/agentic-testops@main
        with:
          project: "."
          output: reports/agentic-testops-report.md
          json-output: reports/agentic-testops-report.json
          fix-output: reports/agentic-testops-fixes.patch
          rerun-failures: "true"
          suggest-fixes: "true"
          job-summary: "true"
          pytest-args: "tests -q"

      - uses: actions/upload-artifact@v7
        if: always()
        with:
          name: agentic-testops-report
          path: reports/
```

Set `fail-on-test-failure: "false"` when the workflow should collect reports without failing the job. This is useful for scheduled audits, demonstrations, or repositories that want to inspect the generated artifacts before enforcing the result.

Inputs:

- `project`: target project path.
- `output`: Markdown report path.
- `json-output`: JSON report path, or empty to skip JSON.
- `fix-output`: dry-run patch path, or empty to skip patch output.
- `rerun-failures`: whether to rerun parsed failing node IDs.
- `suggest-fixes`: whether to generate dry-run diff suggestions.
- `timeout`: pytest timeout in seconds.
- `pytest-args`: extra pytest arguments parsed with Python `shlex`.
- `fail-on-test-failure`: whether nonzero audit exit code should fail the action.
- `job-summary`: whether to append the Markdown report and patch preview to the GitHub job summary.

Outputs:

- `exit-code`: exit code returned by `agentic-testops`.
- `report-path`: Markdown report path.
- `json-path`: JSON report path.
- `fix-path`: dry-run patch path.
- `summary-written`: whether the action wrote to `$GITHUB_STEP_SUMMARY`.
