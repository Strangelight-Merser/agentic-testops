"""Replay real upstream bug fixes and audit each broken state.

Methodology (SWE-bench style "revert source, keep tests"):

1. Clone the upstream repository and check out a real bug-fix commit that
   touched both implementation and tests.
2. Restore only the implementation files from the fix commit's parent, keeping
   the regression tests from the fix itself.
3. The working tree now reproduces the historical bug exactly as users hit it.
4. Run ``agentic-testops audit`` against that tree and save the artifacts.

This keeps the evaluation honest: the failures are real, written by other
maintainers, and were never used to design this tool's diagnosis rules.

Usage:

    python scripts/evaluate_real_world.py --workdir /tmp/ato-eval --output reports/real-world
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Case:
    name: str
    repo_url: str
    fix_commit: str
    source_paths: list[str]
    notes: str = ""
    expect_collection_failure: bool = False
    clone_depth: int = 300
    extra_audit_args: list[str] = field(default_factory=list)


CASES = [
    Case(
        name="more-itertools-reversed-numeric-range",
        repo_url="https://github.com/more-itertools/more-itertools.git",
        fix_commit="edb3346",
        source_paths=["more_itertools"],
        notes="Fix empty ranges in numeric_range.__reversed__ (IndexError regression).",
    ),
    Case(
        name="more-itertools-repeat-with-iterators",
        repo_url="https://github.com/more-itertools/more-itertools.git",
        fix_commit="be5793a",
        source_paths=["more_itertools"],
        notes="Two fixes for repeat with iterator arguments (behavioral regression).",
    ),
    Case(
        name="more-itertools-nth-combination-exception",
        repo_url="https://github.com/more-itertools/more-itertools.git",
        fix_commit="06f3181",
        source_paths=["more_itertools"],
        notes="nth_combination_with_replacement raised the wrong exception type.",
    ),
    Case(
        name="tabulate-asciidoc-trailing-whitespace",
        repo_url="https://github.com/astanin/python-tabulate.git",
        fix_commit="3aa568c",
        source_paths=["tabulate"],
        notes="asciidoc output emitted trailing whitespace (assertion regressions).",
    ),
    Case(
        name="boltons-modern-pytest-collection",
        repo_url="https://github.com/mahmoud/boltons.git",
        fix_commit="HEAD",
        source_paths=[],
        notes=(
            "No source revert: boltons' conftest uses pytest hooks removed in "
            "modern pytest, a realistic collection/environment failure."
        ),
        expect_collection_failure=True,
    ),
]


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)


def prepare_case(case: Case, workdir: Path) -> Path:
    repo_dir = workdir / case.name
    if not repo_dir.exists():
        clone = run(
            ["git", "clone", "--quiet", "--depth", str(case.clone_depth), case.repo_url, str(repo_dir)]
        )
        if clone.returncode != 0:
            raise RuntimeError(f"clone failed for {case.name}: {clone.stderr.strip()}")
    checkout = run(["git", "checkout", "-qf", case.fix_commit], cwd=repo_dir)
    if checkout.returncode != 0:
        raise RuntimeError(f"checkout failed for {case.name}: {checkout.stderr.strip()}")
    for source_path in case.source_paths:
        revert = run(["git", "checkout", "-q", f"{case.fix_commit}^", "--", source_path], cwd=repo_dir)
        if revert.returncode != 0:
            raise RuntimeError(f"source revert failed for {case.name}: {revert.stderr.strip()}")
    return repo_dir


def audit_case(case: Case, repo_dir: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "agentic_testops.cli",
        "audit",
        str(repo_dir),
        "-o",
        str(output_dir / f"{case.name}.md"),
        "--json-output",
        str(output_dir / f"{case.name}.json"),
        *case.extra_audit_args,
    ]
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, default=Path("/tmp/ato-eval"))
    parser.add_argument("--output", type=Path, default=Path("reports/real-world"))
    parser.add_argument("--case", action="append", help="Run only the named case(s).")
    args = parser.parse_args(argv)

    selected = [case for case in CASES if not args.case or case.name in args.case]
    if not selected:
        print(f"No matching cases. Known: {[case.name for case in CASES]}")
        return 2

    args.workdir.mkdir(parents=True, exist_ok=True)
    overall = 0
    for case in selected:
        print(f"== {case.name}: {case.notes}")
        repo_dir = prepare_case(case, args.workdir)
        returncode = audit_case(case, repo_dir, args.output)
        print(f"   audit exit code: {returncode}")
        if returncode not in (0, 1):
            overall = returncode
    return overall


if __name__ == "__main__":
    raise SystemExit(main())
