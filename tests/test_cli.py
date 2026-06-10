import subprocess
import sys
from pathlib import Path

from agentic_testops import cli
from agentic_testops.models import FixSuggestion, TestRun


def test_module_entrypoint_shows_help() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "agentic_testops.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "agentic-testops" in completed.stdout


def test_rerun_preserves_user_pytest_args(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_run_pytest(project_path: Path, extra_args=None, timeout=120):
        calls.append(list(extra_args or []))
        return TestRun(
            command=["python", "-m", "pytest", *(extra_args or [])],
            cwd=project_path,
            returncode=1,
            stdout="FAILED tests/test_app.py::test_case - AssertionError: assert False\n",
            stderr="",
            duration_seconds=0.1,
        )

    monkeypatch.setattr(cli, "run_pytest", fake_run_pytest)

    exit_code = cli.main(
        [
            "audit",
            str(tmp_path),
            "--rerun-failures",
            "--pytest-arg=-k",
            "--pytest-arg=slow",
            "-o",
            str(tmp_path / "report.md"),
        ]
    )

    assert exit_code == 1
    assert calls[0] == ["-k", "slow"]
    assert calls[1] == ["-k", "slow", "tests/test_app.py::test_case"]


def test_pytest_arg_accepts_values_that_start_with_dash(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_run_pytest(project_path: Path, extra_args=None, timeout=120):
        calls.append(list(extra_args or []))
        return TestRun(
            command=["python", "-m", "pytest", *(extra_args or [])],
            cwd=project_path,
            returncode=0,
            stdout="1 passed\n",
            stderr="",
            duration_seconds=0.1,
        )

    monkeypatch.setattr(cli, "run_pytest", fake_run_pytest)

    exit_code = cli.main(["audit", str(tmp_path), "--pytest-arg", "tests/test_parser.py", "--pytest-arg=-q"])

    assert exit_code == 0
    assert calls[0] == ["tests/test_parser.py", "-q"]


def test_fix_output_writes_dry_run_suggestions(monkeypatch, tmp_path) -> None:
    def fake_run_pytest(project_path: Path, extra_args=None, timeout=120):
        return TestRun(
            command=["python", "-m", "pytest"],
            cwd=project_path,
            returncode=1,
            stdout="FAILED tests/test_app.py::test_case - AssertionError: assert False\n",
            stderr="",
            duration_seconds=0.1,
        )

    def fake_suggest_fixes(project_path, diagnoses, patch_proposals):
        return [
            FixSuggestion(
                failure_nodeid="tests/test_app.py::test_case",
                target_file="app.py",
                title="Patch behavior",
                explanation="Dry-run only.",
                confidence="medium",
                diff="--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new",
                guardrail_tests=["tests/test_app.py::test_case"],
            )
        ]

    monkeypatch.setattr(cli, "run_pytest", fake_run_pytest)
    monkeypatch.setattr(cli, "suggest_fixes", fake_suggest_fixes)

    fix_output = tmp_path / "fixes.patch"
    exit_code = cli.main(["audit", str(tmp_path), "-o", str(tmp_path / "report.md"), "--fix-output", str(fix_output)])

    assert exit_code == 1
    assert "--- a/app.py" in fix_output.read_text(encoding="utf-8")
