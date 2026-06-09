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


def test_diagnose_name_error_as_symbol_resolution() -> None:
    failure = Failure(
        nodeid="tests/test_app.py::test_total",
        headline="NameError: name 'subtotal' is not defined",
        file_path="app.py",
        line_number=12,
        error_type="NameError",
        detail="app.py:12: in total\nE   NameError: name 'subtotal' is not defined",
    )
    run = TestRun(["python", "-m", "pytest"], Path("."), 1, "", "", 0.1)

    diagnoses = diagnose_failures([failure], run)

    assert diagnoses[0].category == "symbol-resolution"
    assert "not defined" in diagnoses[0].summary
    assert diagnoses[0].repair_advice


def test_diagnose_attribute_error_as_object_interface() -> None:
    failure = Failure(
        nodeid="tests/test_app.py::test_user_name",
        headline="AttributeError: 'dict' object has no attribute 'name'",
        file_path="app.py",
        line_number=8,
        error_type="AttributeError",
        detail="app.py:8: in user_name\nE   AttributeError: 'dict' object has no attribute 'name'",
    )
    run = TestRun(["python", "-m", "pytest"], Path("."), 1, "", "", 0.1)

    diagnoses = diagnose_failures([failure], run)

    assert diagnoses[0].category == "object-interface"
    assert "attribute" in diagnoses[0].summary
    assert diagnoses[0].repair_advice


def test_diagnose_file_not_found_as_filesystem_boundary() -> None:
    failure = Failure(
        nodeid="tests/test_app.py::test_load_config",
        headline="FileNotFoundError: [Errno 2] No such file or directory: 'config.toml'",
        file_path="config_loader.py",
        line_number=4,
        error_type="FileNotFoundError",
        detail="config_loader.py:4: in load_config\nE   FileNotFoundError: [Errno 2] No such file or directory: 'config.toml'",
    )
    run = TestRun(["python", "-m", "pytest"], Path("."), 1, "", "", 0.1)

    diagnoses = diagnose_failures([failure], run)

    assert diagnoses[0].category == "filesystem-boundary"
    assert "filesystem" in diagnoses[0].summary
    assert diagnoses[0].repair_advice
