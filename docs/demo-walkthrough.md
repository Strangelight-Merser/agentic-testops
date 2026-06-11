# Demo Walkthrough

This walkthrough shows the full loop on the `service_health` example: failing tests become structured diagnoses, focused reruns, patch proposals, and reviewable artifacts.

## Run

```bash
agentic-testops audit examples/service_health \
  --rerun-failures \
  --apply-and-verify \
  -o reports/service-health-report.md \
  --json-output reports/service-health-report.json \
  --fix-output reports/service-health-fixes.patch
```

The example is intentionally broken, so the audit exits with code `1` while still writing all requested artifacts.

## Signal Extracted

| Failure | Category | Patch target |
| --- | --- | --- |
| Missing config file | `filesystem-boundary` | `service_health.py:9` |
| Dictionary used where an object attribute is expected | `object-interface` | `service_health.py:15` |
| Missing `subtotal` name in invoice calculation | `symbol-resolution` | `service_health.py:20` |

## Artifacts

- [Markdown report](sample-service-health-report.md)
- [Machine-readable JSON](sample-service-health-report.json)
- [Dry-run patch output](sample-service-health-fixes.patch)

The dry-run patch contains three reviewable hunks. With `--apply-and-verify`, the audit applies them to a temporary copy of `examples/service_health`, reruns the three guardrail tests and then the full suite there, and records the outcome in the report's Fix Verification section — for this example, a `fix-confirmed` verdict with the full suite passing. The original example stays broken on disk, as intended.

## Why It Matters

The report preserves evidence from pytest, reruns only the parsed failing node IDs, and keeps repair recommendations reviewable. The base system is deterministic and requires no API key, so it can run in local development or CI before any optional code-fixing layer is added.
