from __future__ import annotations

from .models import Diagnosis, Failure, TestRun


def diagnose_failures(failures: list[Failure], run: TestRun) -> list[Diagnosis]:
    if run.timed_out:
        return [_diagnose_timeout(run)]
    if not failures and not run.passed:
        return [_diagnose_collection_or_environment(run)]
    return [_diagnose_failure(failure) for failure in failures]


def _diagnose_timeout(run: TestRun) -> Diagnosis:
    text = f"{run.stdout}\n{run.stderr}"
    failure = Failure(
        nodeid="pytest session",
        headline="Pytest timed out before the test session completed.",
        detail=text[-2000:],
    )
    return Diagnosis(
        failure=failure,
        category="timeout",
        confidence="high",
        summary="The test command exceeded the configured timeout, so the project may contain a hanging test or slow fixture.",
        evidence=_interesting_lines(text),
        repair_advice=[
            "Rerun with a higher timeout only after checking whether the suite is expected to take that long.",
            "Use pytest selection such as `-k` or a single test path to isolate the hanging test.",
            "Inspect long-running fixtures, network calls, sleeps, and subprocess waits first.",
        ],
    )


def _diagnose_collection_or_environment(run: TestRun) -> Diagnosis:
    text = f"{run.stdout}\n{run.stderr}"
    failure = Failure(
        nodeid="pytest session",
        headline="Pytest did not complete successfully before individual test failures were parsed.",
        detail=text[-2000:],
    )
    if "No module named pytest" in text:
        return Diagnosis(
            failure=failure,
            category="environment",
            confidence="high",
            summary="pytest is not installed in the active Python environment.",
            evidence=["The command output contains 'No module named pytest'."],
            repair_advice=[
                "Install development dependencies with `python -m pip install -e .[dev]`.",
                "Run the audit again from the same virtual environment.",
            ],
        )
    return Diagnosis(
        failure=failure,
        category="collection-or-environment",
        confidence="medium",
        summary="The test session failed before a normal failure summary could be extracted.",
        evidence=_interesting_lines(text),
        repair_advice=[
            "Read the collection traceback first; collection failures usually come from import errors, syntax errors, or missing fixtures.",
            "Run `python -m pytest -q` in the target project to reproduce the same failure directly.",
        ],
    )


def _diagnose_failure(failure: Failure) -> Diagnosis:
    text = f"{failure.headline}\n{failure.detail}"
    error = failure.error_type or ""

    if "ZeroDivisionError" in error or "ValueError" in error:
        return Diagnosis(
            failure=failure,
            category="input-validation",
            confidence="medium",
            summary="The implementation likely misses validation for an invalid or boundary input.",
            evidence=_interesting_lines(text),
            repair_advice=[
                "Define the intended behavior for the boundary input: reject, clamp, or return a neutral value.",
                "Guard the operation close to the source of the invalid value.",
                "Document the behavior in a test so future agents preserve it.",
            ],
        )

    if "ModuleNotFoundError" in error or "ImportError" in error:
        return Diagnosis(
            failure=failure,
            category="dependency-or-import",
            confidence="high",
            summary="The project cannot import a required module or symbol.",
            evidence=_interesting_lines(text),
            repair_advice=[
                "Check whether the missing package belongs in project dependencies or test extras.",
                "If the import is local, verify package layout, `__init__.py`, and the test command working directory.",
                "Prefer fixing import paths or packaging metadata over mutating `sys.path` inside tests.",
            ],
        )

    if "TypeError" in error:
        return Diagnosis(
            failure=failure,
            category="api-contract",
            confidence="medium",
            summary="The failing call does not match the function or method contract.",
            evidence=_interesting_lines(text),
            repair_advice=[
                "Inspect the callee signature and the failing call site together.",
                "If the public API changed, update compatibility shims or tests intentionally.",
                "Add a regression test for the argument pattern that triggered the TypeError.",
            ],
        )

    if "KeyError" in error or "IndexError" in error:
        return Diagnosis(
            failure=failure,
            category="data-shape",
            confidence="medium",
            summary="The code accessed data that was missing or had an unexpected shape.",
            evidence=_interesting_lines(text),
            repair_advice=[
                "Validate the input fixture or runtime data shape before the failing access.",
                "Use explicit error handling or default behavior only if that matches the product contract.",
                "Add a test for empty, missing, or malformed data.",
            ],
        )

    if "AssertionError" in error or "assert " in text:
        return Diagnosis(
            failure=failure,
            category="behavioral-regression",
            confidence="medium",
            summary="A test assertion failed, so the implementation likely violates the expected behavior.",
            evidence=_interesting_lines(text),
            repair_advice=[
                "Compare expected and actual values in the failing assertion before changing the test.",
                "Add or update a narrow unit test around the boundary condition that produced the mismatch.",
                "Patch the implementation path exercised by the failing nodeid, then rerun only this test first.",
            ],
        )

    return Diagnosis(
        failure=failure,
        category="unknown",
        confidence="low",
        summary="The failure did not match a built-in diagnosis rule.",
        evidence=_interesting_lines(text),
        repair_advice=[
            "Read the nearest traceback frame inside the project, not only the pytest wrapper frame.",
            "Reduce the failing test to the smallest input that still reproduces the issue.",
            "Add a project-specific diagnosis rule once the root cause is known.",
        ],
    )


def _interesting_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("E   ", ">", "FAILED", "ImportError", "ModuleNotFoundError")) or ".py:" in line:
            lines.append(line[:240])
        if len(lines) >= 5:
            break
    return lines or [text.strip().splitlines()[0][:240]] if text.strip() else []
