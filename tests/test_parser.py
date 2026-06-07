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


def test_parse_traceback_keeps_real_error_type_and_project_frame() -> None:
    run = TestRun(
        command=["python", "-m", "pytest"],
        cwd=Path("."),
        returncode=1,
        stdout="""F                                                                        [100%]
=================================== FAILURES ===================================
___________________________ test_divide_rejects_zero ___________________________
test_calculator.py:8: in test_divide_rejects_zero
    divide(10, 0)
calculator.py:2: in divide
    return a / b
           ^^^^^
E   ZeroDivisionError: division by zero
=========================== short test summary info ============================
FAILED test_calculator.py::test_divide_rejects_zero - ZeroDivisionError: divi...
""",
        stderr="",
        duration_seconds=0.1,
    )

    failures = parse_failures(run)

    assert failures[0].nodeid == "test_calculator.py::test_divide_rejects_zero"
    assert failures[0].error_type == "ZeroDivisionError"
    assert failures[0].file_path == "calculator.py"
    assert failures[0].line_number == 2


def test_parse_class_based_nodeid_from_summary() -> None:
    run = TestRun(
        command=["python", "-m", "pytest"],
        cwd=Path("."),
        returncode=1,
        stdout="""F                                                                        [100%]
=================================== FAILURES ===================================
____________________________ TestMath.test_add ____________________________
tests/test_math.py:6: in test_add
    assert add(1, 2) == 4
E   AssertionError: assert 3 == 4
=========================== short test summary info ============================
FAILED tests/test_math.py::TestMath::test_add - AssertionError: assert 3 == 4
""",
        stderr="",
        duration_seconds=0.1,
    )

    failures = parse_failures(run)

    assert failures[0].nodeid == "tests/test_math.py::TestMath::test_add"
    assert failures[0].error_type == "AssertionError"
