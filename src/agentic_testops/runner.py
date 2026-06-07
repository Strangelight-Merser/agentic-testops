from __future__ import annotations

import subprocess
import sys
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
    try:
        completed = subprocess.run(
            command,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - start
        stdout = _coerce_output(exc.stdout)
        stderr = _coerce_output(exc.stderr)
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
        )

    duration = time.perf_counter() - start
    return TestRun(
        command=command,
        cwd=project_path,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=duration,
    )


def _coerce_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output
