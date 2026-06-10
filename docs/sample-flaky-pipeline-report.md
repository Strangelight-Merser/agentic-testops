# Agentic TestOps Audit Report

- Project: `examples/flaky_pipeline`
- Status: **FAIL**
- Command: `python -m pytest --tb=short -q`
- Duration: `0.10s`
- Return code: `1`
- Parsed failures: `2`
- Structured results: `JUnit XML`

## Flakiness Check

Failing tests were rerun in isolation to separate unstable failures from reproducible ones.

| Test | Reruns | Failed | Verdict |
| --- | --- | --- | --- |
| `test_pipeline.py::test_fetch_rates_includes_eur` | 2 | 0 | `flaky` |
| `test_pipeline.py::test_convert_applies_rate_exactly` | 2 | 2 | `consistent` |

Flaky failures usually indicate test order, timing, or shared-state issues. Treat their patch proposals below with extra caution.

## Diagnosis

### 1. `test_pipeline.py::test_fetch_rates_includes_eur`

- Headline: AssertionError: assert 'EUR' in {'USD': 1.0} at `test_pipeline.py`:8
- Category: `behavioral-regression`
- Confidence: `medium`
- Summary: A test assertion failed, so the implementation likely violates the expected behavior.

Evidence:
- `test_pipeline.py:8: in test_fetch_rates_includes_eur`
- `E   AssertionError: assert 'EUR' in {'USD': 1.0}`

Repair advice:
- Compare expected and actual values in the failing assertion before changing the test.
- Add or update a narrow unit test around the boundary condition that produced the mismatch.
- Patch the implementation path exercised by the failing nodeid, then rerun only this test first.

### 2. `test_pipeline.py::test_convert_applies_rate_exactly`

- Headline: assert 21.0 == 20.0
 +  where 21.0 = convert(10.0, 2.0) at `test_pipeline.py`:12
- Category: `behavioral-regression`
- Confidence: `medium`
- Summary: A test assertion failed, so the implementation likely violates the expected behavior.

Evidence:
- `test_pipeline.py:12: in test_convert_applies_rate_exactly`
- `E   assert 21.0 == 20.0`
- `E    +  where 21.0 = convert(10.0, 2.0)`

Repair advice:
- Compare expected and actual values in the failing assertion before changing the test.
- Add or update a narrow unit test around the boundary condition that produced the mismatch.
- Patch the implementation path exercised by the failing nodeid, then rerun only this test first.

## Patch Proposals

### 1. `test_pipeline.py::test_fetch_rates_includes_eur`

- Target: `test_pipeline.py:8`
- Confidence: `low`
- Action: Inspect the nearest project frame and make the smallest code change that satisfies the failing test contract.
- Rationale: No higher-confidence domain rule matched this failure, so the proposal stays conservative.
- Guardrail tests:
  - `test_pipeline.py::test_fetch_rates_includes_eur`

### 2. `test_pipeline.py::test_convert_applies_rate_exactly`

- Target: `test_pipeline.py:12`
- Confidence: `low`
- Action: Inspect the nearest project frame and make the smallest code change that satisfies the failing test contract.
- Rationale: No higher-confidence domain rule matched this failure, so the proposal stays conservative.
- Guardrail tests:
  - `test_pipeline.py::test_convert_applies_rate_exactly`

## Raw Pytest Output

```text
FF                                                                       [100%]
=================================== FAILURES ===================================
________________________ test_fetch_rates_includes_eur _________________________
test_pipeline.py:8: in test_fetch_rates_includes_eur
    assert "EUR" in rates
E   AssertionError: assert 'EUR' in {'USD': 1.0}
______________________ test_convert_applies_rate_exactly _______________________
test_pipeline.py:12: in test_convert_applies_rate_exactly
    assert convert(10.0, 2.0) == 20.0
E   assert 21.0 == 20.0
E    +  where 21.0 = convert(10.0, 2.0)
=========================== short test summary info ============================
FAILED test_pipeline.py::test_fetch_rates_includes_eur - AssertionError: asse...
FAILED test_pipeline.py::test_convert_applies_rate_exactly - assert 21.0 == 20.0
2 failed in 0.02s
```
