# Agentic TestOps Audit Report

- Project: `examples/service_health`
- Status: **FAIL**
- Command: `python -m pytest --tb=short -q`
- Duration: `0.13s`
- Return code: `1`
- Parsed failures: `3`
- Structured results: `JUnit XML`

## Agentic Rerun

- Status: **FAIL**
- Command: `python -m pytest --tb=short -q test_service_health.py::test_load_config_handles_missing_file test_service_health.py::test_display_name_accepts_dict_user test_service_health.py::test_invoice_total_sums_items_with_tax`
- Duration: `0.13s`

## Diagnosis

### 1. `test_service_health.py::test_load_config_handles_missing_file`

- Headline: FileNotFoundError: Missing config file: missing.env at `service_health.py`:9
- Category: `filesystem-boundary`
- Confidence: `medium`
- Summary: The code crossed a filesystem boundary without handling a missing, inaccessible, or invalid path.

Evidence:
- `test_service_health.py:7: in test_load_config_handles_missing_file`
- `service_health.py:9: in load_config`
- `E   FileNotFoundError: Missing config file: missing.env`

Repair advice:
- Check whether the path should be created, injected as a fixture, or treated as optional input.
- Avoid relying on the process working directory when the project can pass an explicit path.
- Add tests for missing paths, directories, and permission-sensitive behavior where practical.

### 2. `test_service_health.py::test_display_name_accepts_dict_user`

- Headline: AttributeError: 'dict' object has no attribute 'name' at `service_health.py`:15
- Category: `object-interface`
- Confidence: `medium`
- Summary: The code expected an object to expose an attribute or method that is not available at runtime.

Evidence:
- `test_service_health.py:11: in test_display_name_accepts_dict_user`
- `service_health.py:15: in display_name`
- `E   AttributeError: 'dict' object has no attribute 'name'`

Repair advice:
- Compare the runtime object type with the interface the code expects at the failing access.
- If the object shape changed, update the adapter or compatibility layer instead of only changing the test.
- Add a regression test for the object variant that lacks the attribute.

### 3. `test_service_health.py::test_invoice_total_sums_items_with_tax`

- Headline: NameError: name 'subtotal' is not defined at `service_health.py`:20
- Category: `symbol-resolution`
- Confidence: `medium`
- Summary: The implementation referenced a name that is not defined in the active scope.

Evidence:
- `test_service_health.py:15: in test_invoice_total_sums_items_with_tax`
- `service_health.py:20: in invoice_total`
- `E   NameError: name 'subtotal' is not defined`

Repair advice:
- Check whether the missing name should be imported, assigned earlier, or passed as an argument.
- Inspect recent renames around the failing line before adding a new global symbol.
- Add a focused regression test that exercises the code path where the name should be available.

## Patch Proposals

### 1. `test_service_health.py::test_load_config_handles_missing_file`

- Target: `service_health.py:9`
- Confidence: `medium`
- Action: Make the file boundary explicit by validating the path, creating required fixtures, or handling the missing path case.
- Rationale: The traceback shows runtime file access reaching a missing, inaccessible, or invalid path.
- Guardrail tests:
  - `test_service_health.py::test_load_config_handles_missing_file`

### 2. `test_service_health.py::test_display_name_accepts_dict_user`

- Target: `service_health.py:15`
- Confidence: `medium`
- Action: Align the expected object interface by normalizing the input shape or using the interface actually provided at runtime.
- Rationale: The failing access expects an attribute or method that the runtime object does not expose.
- Guardrail tests:
  - `test_service_health.py::test_display_name_accepts_dict_user`

### 3. `test_service_health.py::test_invoice_total_sums_items_with_tax`

- Target: `service_health.py:20`
- Confidence: `medium`
- Action: Resolve the missing symbol by importing, defining, passing, or consistently renaming it near the failing scope.
- Rationale: The code references a name that is unavailable when the failing path executes.
- Guardrail tests:
  - `test_service_health.py::test_invoice_total_sums_items_with_tax`

## Raw Pytest Output

```text
FFF                                                                      [100%]
=================================== FAILURES ===================================
____________________ test_load_config_handles_missing_file _____________________
test_service_health.py:7: in test_load_config_handles_missing_file
    assert load_config("missing.env") == {"raw": ""}
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
service_health.py:9: in load_config
    raise FileNotFoundError(f"Missing config file: {config_path}")
E   FileNotFoundError: Missing config file: missing.env
_____________________ test_display_name_accepts_dict_user ______________________
test_service_health.py:11: in test_display_name_accepts_dict_user
    assert display_name({"name": "ada lovelace"}) == "Ada Lovelace"
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
service_health.py:15: in display_name
    return user.name.title()
           ^^^^^^^^^
E   AttributeError: 'dict' object has no attribute 'name'
____________________ test_invoice_total_sums_items_with_tax ____________________
test_service_health.py:15: in test_invoice_total_sums_items_with_tax
    assert invoice_total([{"amount": 10.0}, {"amount": 5.0}]) == 16.2
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
service_health.py:20: in invoice_total
    return subtotal + (subtotal * tax_rate)
           ^^^^^^^^
E   NameError: name 'subtotal' is not defined
=========================== short test summary info ============================
FAILED test_service_health.py::test_load_config_handles_missing_file - FileNo...
FAILED test_service_health.py::test_display_name_accepts_dict_user - Attribut...
FAILED test_service_health.py::test_invoice_total_sums_items_with_tax - NameE...
3 failed in 0.01s
```
