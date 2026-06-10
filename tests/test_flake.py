from pathlib import Path

import pytest

from agentic_testops import cli
from agentic_testops.flake import detect_flaky_failures
from agentic_testops.models import AuditReport, Failure, FlakeResult, TestRun
from agentic_testops.reporter import render_markdown


def _failure(nodeid: str) -> Failure:
    return Failure(nodeid=nodeid, headline="AssertionError: assert False")


def _run(returncode: int, stdout: str = "") -> TestRun:
    return TestRun(
        command=["python", "-m", "pytest"],
        cwd=Path("."),
        returncode=returncode,
        stdout=stdout,
        stderr="",
        duration_seconds=0.1,
    )


def _failing_run(*nodeids: str) -> TestRun:
    lines = "".join(f"FAILED {nodeid} - AssertionError: assert False\n" for nodeid in nodeids)
    return _run(returncode=1, stdout=lines)


def test_consistent_failure_fails_every_attempt() -> None:
    runs = [_failing_run("tests/test_app.py::test_case") for _ in range(3)]

    results = detect_flaky_failures(
        Path("."),
        [_failure("tests/test_app.py::test_case")],
        attempts=3,
        runner=lambda *args, **kwargs: runs.pop(0),
    )

    assert results == [
        FlakeResult(
            nodeid="tests/test_app.py::test_case",
            attempts=3,
            failed_attempts=3,
            verdict="consistent",
        )
    ]
    assert results[0].pass_rate == 0.0


def test_intermittent_failure_is_flaky() -> None:
    runs = [
        _failing_run("tests/test_app.py::test_case"),
        _run(returncode=0, stdout="1 passed\n"),
        _failing_run("tests/test_app.py::test_case"),
    ]

    results = detect_flaky_failures(
        Path("."),
        [_failure("tests/test_app.py::test_case")],
        attempts=3,
        runner=lambda *args, **kwargs: runs.pop(0),
    )

    assert results[0].verdict == "flaky"
    assert results[0].failed_attempts == 2
    assert results[0].pass_rate == pytest.approx(1 / 3)


def test_mixed_tests_classified_independently() -> None:
    runs = [
        _failing_run("tests/test_app.py::test_stable", "tests/test_app.py::test_shaky"),
        _failing_run("tests/test_app.py::test_stable"),
    ]

    results = detect_flaky_failures(
        Path("."),
        [_failure("tests/test_app.py::test_stable"), _failure("tests/test_app.py::test_shaky")],
        attempts=2,
        runner=lambda *args, **kwargs: runs.pop(0),
    )

    verdicts = {result.nodeid: result.verdict for result in results}
    assert verdicts == {
        "tests/test_app.py::test_stable": "consistent",
        "tests/test_app.py::test_shaky": "flaky",
    }


def test_timed_out_attempt_counts_as_failed() -> None:
    timeout_run = TestRun(
        command=["python", "-m", "pytest"],
        cwd=Path("."),
        returncode=124,
        stdout="",
        stderr="Pytest timed out after 120 seconds.",
        duration_seconds=120.0,
        timed_out=True,
    )

    results = detect_flaky_failures(
        Path("."),
        [_failure("tests/test_app.py::test_case")],
        attempts=1,
        runner=lambda *args, **kwargs: timeout_run,
    )

    assert results[0].verdict == "consistent"
    assert results[0].failed_attempts == 1


def test_nodeid_path_suffix_matches_across_parse_sources() -> None:
    runs = [_failing_run("test_app.py::test_case")]

    results = detect_flaky_failures(
        Path("."),
        [_failure("tests/test_app.py::test_case")],
        attempts=1,
        runner=lambda *args, **kwargs: runs.pop(0),
    )

    assert results[0].verdict == "consistent"


def test_same_test_name_in_other_file_does_not_match() -> None:
    runs = [_failing_run("tests/test_other.py::test_case")]

    results = detect_flaky_failures(
        Path("."),
        [_failure("tests/test_app.py::test_case")],
        attempts=1,
        runner=lambda *args, **kwargs: runs.pop(0),
    )

    assert results[0].verdict == "flaky"
    assert results[0].failed_attempts == 0


def test_attempts_must_be_positive() -> None:
    with pytest.raises(ValueError):
        detect_flaky_failures(Path("."), [_failure("tests/test_app.py::test_case")], attempts=0)


def test_no_failures_returns_empty() -> None:
    assert detect_flaky_failures(Path("."), [], attempts=3) == []


def test_cli_detect_flaky_runs_extra_attempts(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_run_pytest(project_path: Path, extra_args=None, timeout=120):
        calls.append(list(extra_args or []))
        return _failing_run("tests/test_app.py::test_case")

    monkeypatch.setattr(cli, "run_pytest", fake_run_pytest)
    monkeypatch.setattr("agentic_testops.flake.run_pytest", fake_run_pytest)

    exit_code = cli.main(
        [
            "audit",
            str(tmp_path),
            "--detect-flaky",
            "2",
            "-o",
            str(tmp_path / "report.md"),
            "--json-output",
            str(tmp_path / "report.json"),
        ]
    )

    assert exit_code == 1
    # 1 initial run + 2 flake-detection attempts.
    assert len(calls) == 3
    assert calls[1] == ["tests/test_app.py::test_case"]
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "## Flakiness Check" in report_text
    assert "`consistent`" in report_text
    json_text = (tmp_path / "report.json").read_text(encoding="utf-8")
    assert '"verdict": "consistent"' in json_text


def test_markdown_report_warns_about_flaky_failures() -> None:
    failure = _failure("tests/test_app.py::test_case")
    report = AuditReport(
        project_path=Path("demo"),
        run=_failing_run(failure.nodeid),
        failures=[failure],
        diagnoses=[],
        flake_results=[
            FlakeResult(nodeid=failure.nodeid, attempts=3, failed_attempts=1, verdict="flaky")
        ],
    )

    text = render_markdown(report)

    assert "## Flakiness Check" in text
    assert "| `tests/test_app.py::test_case` | 3 | 1 | `flaky` |" in text
    assert "extra caution" in text
