# Agentic TestOps Audit Report

- Project: `tabulate-asciidoc-trailing-whitespace`
- Status: **FAIL**
- Command: `python -m pytest --tb=short -q`
- Duration: `1.10s`
- Return code: `1`
- Parsed failures: `3`
- Structured results: `JUnit XML`

## Diagnosis

### 1. `test/test_output.py::test_asciidoc`

- Headline: AssertionError at `test/common.py`:10
- Category: `behavioral-regression`
- Confidence: `medium`
- Summary: A test assertion failed, so the implementation likely violates the expected behavior.

Evidence:
- `test/test_output.py:2098: in test_asciidoc`
- `test/common.py:10: in assert_equal`
- `E   AssertionError`

Repair advice:
- Compare expected and actual values in the failing assertion before changing the test.
- Add or update a narrow unit test around the boundary condition that produced the mismatch.
- Patch the implementation path exercised by the failing nodeid, then rerun only this test first.

### 2. `test/test_output.py::test_asciidoc_headerless`

- Headline: AssertionError at `test/common.py`:10
- Category: `behavioral-regression`
- Confidence: `medium`
- Summary: A test assertion failed, so the implementation likely violates the expected behavior.

Evidence:
- `test/test_output.py:2113: in test_asciidoc_headerless`
- `test/common.py:10: in assert_equal`
- `E   AssertionError`

Repair advice:
- Compare expected and actual values in the failing assertion before changing the test.
- Add or update a narrow unit test around the boundary condition that produced the mismatch.
- Patch the implementation path exercised by the failing nodeid, then rerun only this test first.

### 3. `test/test_regression.py::test_asciidoc_without_trailing_whitespace`

- Headline: AssertionError at `test/common.py`:10
- Category: `behavioral-regression`
- Confidence: `medium`
- Summary: A test assertion failed, so the implementation likely violates the expected behavior.

Evidence:
- `test/test_regression.py:589: in test_asciidoc_without_trailing_whitespace`
- `test/common.py:10: in assert_equal`
- `E   AssertionError`

Repair advice:
- Compare expected and actual values in the failing assertion before changing the test.
- Add or update a narrow unit test around the boundary condition that produced the mismatch.
- Patch the implementation path exercised by the failing nodeid, then rerun only this test first.

## Patch Proposals

### 1. `test/test_output.py::test_asciidoc`

- Target: `test/common.py:10`
- Confidence: `low`
- Action: Inspect the nearest project frame and make the smallest code change that satisfies the failing test contract.
- Rationale: No higher-confidence domain rule matched this failure, so the proposal stays conservative.
- Guardrail tests:
  - `test/test_output.py::test_asciidoc`

### 2. `test/test_output.py::test_asciidoc_headerless`

- Target: `test/common.py:10`
- Confidence: `low`
- Action: Inspect the nearest project frame and make the smallest code change that satisfies the failing test contract.
- Rationale: No higher-confidence domain rule matched this failure, so the proposal stays conservative.
- Guardrail tests:
  - `test/test_output.py::test_asciidoc_headerless`

### 3. `test/test_regression.py::test_asciidoc_without_trailing_whitespace`

- Target: `test/common.py:10`
- Confidence: `low`
- Action: Inspect the nearest project frame and make the smallest code change that satisfies the failing test contract.
- Rationale: No higher-confidence domain rule matched this failure, so the proposal stays conservative.
- Guardrail tests:
  - `test/test_regression.py::test_asciidoc_without_trailing_whitespace`

## Raw Pytest Output

```text
..........sssssssssssssssss............................................. [ 21%]
..s..s.............s.......................s......s......s......s......s [ 42%]
......s......s.......s....s..s..s..s..s..s..s...........FF.............. [ 63%]
..............................s......................................... [ 84%]
............ss...................F...sss.....s.....ss                    [100%]
=================================== FAILURES ===================================
________________________________ test_asciidoc _________________________________
test/test_output.py:2098: in test_asciidoc
    assert_equal(expected, result)
test/common.py:10: in assert_equal
    assert expected == result
E   AssertionError
----------------------------- Captured stdout call -----------------------------
Expected:
'[cols="<11,>11",options="header"]\n|====\n| strings   |   numbers\n| spam      |   41.9999\n| eggs      |  451\n|===='

Got:
'[cols="<11,>11",options="header"]\n|====\n| strings   |   numbers \n| spam      |   41.9999 \n| eggs      |  451      \n|===='

___________________________ test_asciidoc_headerless ___________________________
test/test_output.py:2113: in test_asciidoc_headerless
    assert_equal(expected, result)
test/common.py:10: in assert_equal
    assert expected == result
E   AssertionError
----------------------------- Captured stdout call -----------------------------
Expected:
'[cols="<6,>10"]\n|====\n| spam |  41.9999\n| eggs | 451\n|===='

Got:
'[cols="<6,>10"]\n|====\n| spam |  41.9999 \n| eggs | 451      \n|===='

__________________ test_asciidoc_without_trailing_whitespace ___________________
test/test_regression.py:589: in test_asciidoc_without_trailing_whitespace
    assert_equal(expected, result)
test/common.py:10: in assert_equal
    assert expected == result
E   AssertionError
----------------------------- Captured stdout call -----------------------------
Expected:
'[cols="<14",options="header"]\n|====\n| longheader\n| foo\n|===='

Got:
'[cols="<14",options="header"]\n|====\n| longheader   \n| foo          \n|===='

=========================== short test summary info ============================
FAILED test/test_output.py::test_asciidoc - AssertionError
FAILED test/test_output.py::test_asciidoc_headerless - AssertionError
FAILED test/test_regression.py::test_asciidoc_without_trailing_whitespace - A...
3 failed, 294 passed, 44 skipped in 0.98s
```
