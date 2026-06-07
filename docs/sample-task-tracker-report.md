# Agentic TestOps Audit Report

- Project: `examples/task_tracker`
- Status: **FAIL**
- Command: `python -m pytest --tb=short -q`
- Duration: `0.12s`
- Return code: `1`
- Parsed failures: `3`

## Agentic Rerun

- Status: **FAIL**
- Command: `python -m pytest --tb=short -q test_task_tracker.py::test_create_task_accepts_priority_metadata test_task_tracker.py::test_completion_rate_uses_done_field test_task_tracker.py::test_next_task_handles_empty_backlog`
- Duration: `0.11s`

## Diagnosis

### 1. `test_task_tracker.py::test_create_task_accepts_priority_metadata`

- Headline: TypeError: create_task() got an unexpected keyword argument 'priority' at `test_task_tracker.py`:5
- Category: `api-contract`
- Confidence: `medium`
- Summary: The failing call does not match the function or method contract.

Evidence:
- `test_task_tracker.py:5: in test_create_task_accepts_priority_metadata`
- `E   TypeError: create_task() got an unexpected keyword argument 'priority'`

Repair advice:
- Inspect the callee signature and the failing call site together.
- If the public API changed, update compatibility shims or tests intentionally.
- Add a regression test for the argument pattern that triggered the TypeError.

### 2. `test_task_tracker.py::test_completion_rate_uses_done_field`

- Headline: KeyError: 'completed' at `task_tracker.py`:6
- Category: `data-shape`
- Confidence: `medium`
- Summary: The code accessed data that was missing or had an unexpected shape.

Evidence:
- `test_task_tracker.py:17: in test_completion_rate_uses_done_field`
- `task_tracker.py:6: in completion_rate`
- `task_tracker.py:6: in <genexpr>`
- `E   KeyError: 'completed'`

Repair advice:
- Validate the input fixture or runtime data shape before the failing access.
- Use explicit error handling or default behavior only if that matches the product contract.
- Add a test for empty, missing, or malformed data.

### 3. `test_task_tracker.py::test_next_task_handles_empty_backlog`

- Headline: IndexError: list index out of range at `task_tracker.py`:12
- Category: `data-shape`
- Confidence: `medium`
- Summary: The code accessed data that was missing or had an unexpected shape.

Evidence:
- `test_task_tracker.py:21: in test_next_task_handles_empty_backlog`
- `task_tracker.py:12: in next_task`
- `E   IndexError: list index out of range`

Repair advice:
- Validate the input fixture or runtime data shape before the failing access.
- Use explicit error handling or default behavior only if that matches the product contract.
- Add a test for empty, missing, or malformed data.

## Patch Proposals

### 1. `test_task_tracker.py::test_create_task_accepts_priority_metadata`

- Target: `task_tracker.py:1`
- Confidence: `medium`
- Action: Align the failing call and callee signature, preserving compatibility if the function is public.
- Rationale: The error indicates callers and implementation disagree about accepted arguments or return shape.
- Guardrail tests:
  - `test_task_tracker.py::test_create_task_accepts_priority_metadata`

### 2. `test_task_tracker.py::test_completion_rate_uses_done_field`

- Target: `task_tracker.py:6`
- Confidence: `medium`
- Action: Normalize or validate the data shape before reading required keys or indexes.
- Rationale: The failing code attempted to read data that the test demonstrates may be absent or malformed.
- Guardrail tests:
  - `test_task_tracker.py::test_completion_rate_uses_done_field`

### 3. `test_task_tracker.py::test_next_task_handles_empty_backlog`

- Target: `task_tracker.py:12`
- Confidence: `medium`
- Action: Normalize or validate the data shape before reading required keys or indexes.
- Rationale: The failing code attempted to read data that the test demonstrates may be absent or malformed.
- Guardrail tests:
  - `test_task_tracker.py::test_next_task_handles_empty_backlog`

## Raw Pytest Output

```text
FFF                                                                      [100%]
=================================== FAILURES ===================================
__________________ test_create_task_accepts_priority_metadata __________________
test_task_tracker.py:5: in test_create_task_accepts_priority_metadata
    task = create_task("Ship README", priority=2)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   TypeError: create_task() got an unexpected keyword argument 'priority'
_____________________ test_completion_rate_uses_done_field _____________________
test_task_tracker.py:17: in test_completion_rate_uses_done_field
    assert completion_rate(tasks) == 0.5
           ^^^^^^^^^^^^^^^^^^^^^^
task_tracker.py:6: in completion_rate
    done_count = sum(1 for task in tasks if task["completed"])
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
task_tracker.py:6: in <genexpr>
    done_count = sum(1 for task in tasks if task["completed"])
                                            ^^^^^^^^^^^^^^^^^
E   KeyError: 'completed'
_____________________ test_next_task_handles_empty_backlog _____________________
test_task_tracker.py:21: in test_next_task_handles_empty_backlog
    assert next_task([]) is None
           ^^^^^^^^^^^^^
task_tracker.py:12: in next_task
    return sorted_tasks[0]["title"]
           ^^^^^^^^^^^^^^^
E   IndexError: list index out of range
=========================== short test summary info ============================
FAILED test_task_tracker.py::test_create_task_accepts_priority_metadata - Typ...
FAILED test_task_tracker.py::test_completion_rate_uses_done_field - KeyError:...
FAILED test_task_tracker.py::test_next_task_handles_empty_backlog - IndexErro...
3 failed in 0.01s
```
