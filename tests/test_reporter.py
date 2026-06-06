from pathlib import Path

from agentic_testops.diagnoser import diagnose_failures
from agentic_testops.models import AuditReport, Failure, TestRun
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
