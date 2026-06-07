from pathlib import Path

from agentic_testops.diagnoser import diagnose_failures
from agentic_testops.models import AuditReport, Failure, PatchProposal, TestRun
from agentic_testops.reporter import render_markdown


def test_render_markdown_contains_repair_section() -> None:
    failure = Failure(
        nodeid="test_example.py::test_case",
        headline="ValueError: bad input",
        error_type="ValueError",
        detail="E   ValueError: bad input",
    )
    run = TestRun(["python", "-m", "pytest"], Path("."), 1, "", "", 0.1)
    report = AuditReport(Path(".").resolve(), run, [failure], diagnose_failures([failure], run))

    markdown = render_markdown(report)

    assert "# Agentic TestOps Audit Report" in markdown
    assert "Repair advice" in markdown
    assert "input-validation" in markdown


def test_render_markdown_contains_rerun_and_patch_proposal() -> None:
    failure = Failure(nodeid="test_example.py::test_case", headline="AssertionError", error_type="AssertionError")
    run = TestRun(["python", "-m", "pytest"], Path("."), 1, "failed", "", 0.1)
    rerun = TestRun(["python", "-m", "pytest", "test_example.py::test_case"], Path("."), 1, "failed", "", 0.1)
    proposal = PatchProposal(
        failure_nodeid=failure.nodeid,
        target_file="app.py",
        target_line=10,
        action="Patch the behavior.",
        rationale="The test exposes a regression.",
        confidence="medium",
        guardrail_tests=[failure.nodeid],
    )
    report = AuditReport(
        Path(".").resolve(),
        run,
        [failure],
        diagnose_failures([failure], run),
        patch_proposals=[proposal],
        rerun=rerun,
    )

    markdown = render_markdown(report)

    assert "## Agentic Rerun" in markdown
    assert "## Patch Proposals" in markdown
    assert "app.py:10" in markdown


def test_render_markdown_sanitizes_python_executable_and_marks_timeout() -> None:
    run = TestRun(
        ["/tmp/custom/python", "-m", "pytest", "--tb=short", "-q"],
        Path("."),
        124,
        "",
        "Pytest timed out after 1 seconds.",
        1.0,
        timed_out=True,
    )
    report = AuditReport(Path("."), run, [], diagnose_failures([], run))

    markdown = render_markdown(report)

    assert "Status: **TIMEOUT**" in markdown
    assert "`python -m pytest --tb=short -q`" in markdown
    assert "/tmp/custom/python" not in markdown


def test_json_report_uses_portable_python_command() -> None:
    run = TestRun(["/tmp/custom/python", "-m", "pytest", "-q"], Path("."), 0, "1 passed", "", 0.1)
    report = AuditReport(Path("."), run, [], [])

    data = report.to_dict()

    assert data["command"] == ["python", "-m", "pytest", "-q"]
