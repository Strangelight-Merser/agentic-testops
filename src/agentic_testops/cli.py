from __future__ import annotations

import argparse
from pathlib import Path

from .diagnoser import diagnose_failures
from .fixer import render_fix_suggestions_patch, suggest_fixes
from .flake import detect_flaky_failures
from .models import AuditReport
from .parser import parse_failures
from .patcher import propose_patches
from .reporter import write_json_report, write_markdown_report
from .runner import run_pytest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-testops",
        description="Run pytest, diagnose failures, and generate repair-oriented TestOps reports.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Audit a Python project with pytest.")
    audit.add_argument("project", type=Path, help="Path to the target Python project.")
    audit.add_argument("-o", "--output", type=Path, default=Path("reports/agentic-testops-report.md"))
    audit.add_argument("--json-output", type=Path, help="Optional JSON report path.")
    audit.add_argument("--fix-output", type=Path, help="Optional dry-run fix suggestion patch path.")
    audit.add_argument("--timeout", type=int, default=120, help="Pytest timeout in seconds.")
    audit.add_argument(
        "--rerun-failures",
        action="store_true",
        help="After the first failing run, rerun only parsed failing pytest node IDs.",
    )
    audit.add_argument(
        "--pytest-arg",
        action="append",
        default=[],
        help=(
            "Extra argument passed to pytest. Repeat for multiple args. "
            "Use --pytest-arg=-q for values that start with a dash."
        ),
    )
    audit.add_argument(
        "--detect-flaky",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Rerun each failing test N extra times to separate flaky failures "
            "from consistently reproducible ones. 0 disables detection."
        ),
    )
    audit.add_argument(
        "--suggest-fixes",
        action="store_true",
        help="Generate conservative dry-run unified diff suggestions without modifying the target project.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "audit":
        extra_args = args.pytest_arg
        run = run_pytest(args.project, extra_args=extra_args, timeout=args.timeout)
        failures = parse_failures(run)
        diagnoses = diagnose_failures(failures, run)
        patch_proposals = propose_patches(diagnoses, project_path=args.project)
        should_suggest_fixes = args.suggest_fixes or args.fix_output is not None
        fix_suggestions = suggest_fixes(args.project, diagnoses, patch_proposals) if should_suggest_fixes else []
        rerun = None
        if args.rerun_failures and failures:
            rerun_args = [*extra_args, *[failure.nodeid for failure in failures]]
            rerun = run_pytest(args.project, extra_args=rerun_args, timeout=args.timeout)
        flake_results = []
        if args.detect_flaky > 0 and failures:
            flake_results = detect_flaky_failures(
                args.project,
                failures,
                attempts=args.detect_flaky,
                extra_args=extra_args,
                timeout=args.timeout,
            )
        report = AuditReport(
            project_path=args.project,
            run=run,
            failures=failures,
            diagnoses=diagnoses,
            patch_proposals=patch_proposals,
            fix_suggestions=fix_suggestions,
            rerun=rerun,
            flake_results=flake_results,
        )
        write_markdown_report(report, args.output)
        if args.json_output:
            write_json_report(report, args.json_output)
        if args.fix_output:
            args.fix_output.parent.mkdir(parents=True, exist_ok=True)
            args.fix_output.write_text(render_fix_suggestions_patch(fix_suggestions), encoding="utf-8")

        print(f"Agentic TestOps report written to {args.output}")
        if args.json_output:
            print(f"JSON report written to {args.json_output}")
        if args.fix_output:
            print(f"Dry-run fix suggestions written to {args.fix_output}")
        return 0 if run.passed else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
