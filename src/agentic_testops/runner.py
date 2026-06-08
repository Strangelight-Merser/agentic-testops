from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .models import TestRun


def run_pytest(project_path: Path, extra_args: list[str] | None = None, timeout: int = 120) -> TestRun:
    project_path = project_path.resolve()
    if not project_path.exists():
        raise FileNotFoundError(f"Project path does not exist: {project_path}")
    if not project_path.is_dir():
        raise NotADirectoryError(f"Project path is not a directory: {project_path}")

    command = [sys.executable, "-m", "pytest", "--tb=short", "-q"]
    if extra_args:
        command.extend(extra_args)

    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="agentic-testops-") as temp_dir:
        junit_path = Path(temp_dir) / "junit.xml"
        execution_command = command.copy()
        if not _has_user_junit_arg(extra_args or []):
            execution_command.append(f"--junitxml={junit_path}")

        try:
            completed = subprocess.run(
                execution_command,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - start
            stdout = _strip_internal_junit_line(_coerce_output(exc.stdout))
            stderr = _strip_internal_junit_line(_coerce_output(exc.stderr))
            timeout_message = f"Pytest timed out after {timeout} seconds."
            stderr = "\n".join(part for part in [stderr, timeout_message] if part)
            return TestRun(
                command=command,
                cwd=project_path,
                returncode=124,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
                timed_out=True,
                junit_xml=_read_junit_xml(junit_path),
            )

        duration = time.perf_counter() - start
        return TestRun(
            command=command,
            cwd=project_path,
            returncode=completed.returncode,
            stdout=_strip_internal_junit_line(completed.stdout),
            stderr=_strip_internal_junit_line(completed.stderr),
            duration_seconds=duration,
            junit_xml=_read_junit_xml(junit_path),
        )


def _coerce_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output


def _has_user_junit_arg(extra_args: list[str]) -> bool:
    return any(arg == "--junitxml" or arg.startswith("--junitxml=") for arg in extra_args)


def _read_junit_xml(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _strip_internal_junit_line(output: str) -> str:
    lines = [line for line in output.splitlines() if "generated xml file:" not in line]
    if not lines:
        return ""
    return "\n".join(lines) + ("\n" if output.endswith("\n") else "")
