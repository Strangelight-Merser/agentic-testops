from pathlib import Path

from agentic_testops.diagnoser import diagnose_failures
from agentic_testops.models import Failure, TestRun


def test_diagnose_assertion_failure() -> None:
    failure = Failure(
        nodeid="tests/test_app.py::test_add",
        headline="AssertionError: assert 3 == 4",
        error_type="AssertionError",
        detail="E   AssertionError: assert 3 == 4",
    )
    run = TestRun(["python", "-m", "pytest"], Path("."), 1, "", "", 0.1)

    diagnoses = diagnose_failures([failure], run)

    assert diagnoses[0].category == "behavioral-regression"
    assert diagnoses[0].repair_advice


def test_diagnose_timeout() -> None:
    run = TestRun(
        ["python", "-m", "pytest"],
        Path("."),
        124,
        "",
        "Pytest timed out after 1 seconds.",
        1.0,
        timed_out=True,
    )

    diagnoses = diagnose_failures([], run)

    assert diagnoses[0].category == "timeout"
    assert diagnoses[0].confidence == "high"
