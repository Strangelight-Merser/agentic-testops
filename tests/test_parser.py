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


def test_parse_junit_xml_failure_without_text_output() -> None:
    run = TestRun(
        command=["python", "-m", "pytest"],
        cwd=Path("."),
        returncode=1,
        stdout="",
        stderr="",
        duration_seconds=0.1,
        junit_xml="""<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite tests="1" failures="1">
  <testcase classname="tests.test_math" name="test_add">
    <failure message="AssertionError: assert 3 == 4">tests/test_math.py:4: in test_add
E   AssertionError: assert 3 == 4</failure>
  </testcase>
</testsuite></testsuites>
""",
    )

    failures = parse_failures(run)

    assert failures[0].nodeid == "tests/test_math.py::test_add"
    assert failures[0].headline == "AssertionError: assert 3 == 4"
    assert failures[0].file_path == "tests/test_math.py"
    assert failures[0].line_number == 4


def test_parse_junit_xml_class_based_nodeid() -> None:
    run = TestRun(
        command=["python", "-m", "pytest"],
        cwd=Path("."),
        returncode=1,
        stdout="",
        stderr="",
        duration_seconds=0.1,
        junit_xml="""<testsuites><testsuite tests="1" failures="1">
  <testcase classname="tests.test_math.TestMath" name="test_add">
    <failure message="AssertionError">tests/test_math.py:8: in test_add
E   AssertionError</failure>
  </testcase>
</testsuite></testsuites>
""",
    )

    failures = parse_failures(run)

    assert failures[0].nodeid == "tests/test_math.py::TestMath::test_add"


def test_parse_junit_xml_uses_test_frame_for_nodeid_and_project_frame_for_location() -> None:
    run = TestRun(
        command=["python", "-m", "pytest"],
        cwd=Path("."),
        returncode=1,
        stdout="",
        stderr="",
        duration_seconds=0.1,
        junit_xml="""<testsuites><testsuite tests="1" failures="1">
  <testcase classname="examples.task_tracker.test_task_tracker" name="test_completion_rate_uses_done_field">
    <failure message="KeyError: 'completed'">test_task_tracker.py:17: in test_completion_rate_uses_done_field
    assert completion_rate(tasks) == 0.5
task_tracker.py:6: in completion_rate
    done_count = sum(1 for task in tasks if task["completed"])
E   KeyError: 'completed'</failure>
  </testcase>
</testsuite></testsuites>
""",
    )

    failures = parse_failures(run)

    assert failures[0].nodeid == "test_task_tracker.py::test_completion_rate_uses_done_field"
    assert failures[0].file_path == "task_tracker.py"
    assert failures[0].line_number == 6


def test_parse_junit_xml_prefers_project_frame_over_standard_library_frame() -> None:
    run = TestRun(
        command=["python", "-m", "pytest"],
        cwd=Path("."),
        returncode=1,
        stdout="",
        stderr="",
        duration_seconds=0.1,
        junit_xml="""<testsuites><testsuite tests="1" failures="1">
  <testcase classname="examples.service_health.test_service_health" name="test_load_config_handles_missing_file">
    <failure message="FileNotFoundError: [Errno 2] No such file or directory: 'missing.env'">test_service_health.py:7: in test_load_config_handles_missing_file
    assert load_config("missing.env") == {"raw": ""}
service_health.py:7: in load_config
    text = Path(path).read_text(encoding="utf-8")
/opt/python/lib/pathlib.py:537: in open
    return io.open(self, mode)
E   FileNotFoundError: [Errno 2] No such file or directory: 'missing.env'</failure>
  </testcase>
</testsuite></testsuites>
""",
    )

    failures = parse_failures(run)

    assert failures[0].nodeid == "test_service_health.py::test_load_config_handles_missing_file"
    assert failures[0].file_path == "service_health.py"
    assert failures[0].line_number == 7
