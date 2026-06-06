from pathlib import Path

from agentic_testops.models import TestRun
from agentic_testops.parser import parse_failures


def test_parse_short_pytest_summary() -> None:
    run = TestRun(
        command=["python", "-m", "pytest"],
        cwd=Path("."),
        returncode=1,
        stdout="FAILED tests/test_app.py::test_add - AssertionError: assert 3 == 4\n",
        stderr="",
        duration_seconds=0.1,
    )

    failures = parse_failures(run)

    assert len(failures) == 1
    assert failures[0].nodeid == "tests/test_app.py::test_add"
    assert failures[0].error_type == "AssertionError"


def test_parse_empty_when_passed() -> None:
    run = TestRun(
        command=["python", "-m", "pytest"],
        cwd=Path("."),
        returncode=0,
        stdout="1 passed\n",
        stderr="",
        duration_seconds=0.1,
    )

    assert parse_failures(run) == []
