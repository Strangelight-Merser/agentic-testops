"""Closed-loop verification for dry-run fix suggestions.

The audit pipeline ends with reviewable unified diffs. This module closes the
loop without touching the user's project: the target tree is copied to a
temporary directory, the suggested diffs are applied to the copy, and pytest
is rerun there in two stages — first only the guardrail tests the suggestions
claim to fix, then the full suite to catch collateral damage.

Verdicts:

- ``fix-confirmed``: guardrail tests pass and the full suite introduces no
  failure that was not already present in the baseline run.
- ``fix-ineffective``: at least one guardrail test still fails after the
  patches were applied.
- ``fix-regressed``: guardrail tests pass, but the full suite shows a failure
  that did not exist before the patches.
- ``patch-failed``: a suggested diff did not apply cleanly to the copy, so no
  tests were run.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path

from .flake import _nodeids_match
from .models import Failure, FixSuggestion, TestRun, VerificationResult
from .parser import parse_failures
from .runner import run_pytest

VERDICT_FIX_CONFIRMED = "fix-confirmed"
VERDICT_FIX_INEFFECTIVE = "fix-ineffective"
VERDICT_FIX_REGRESSED = "fix-regressed"
VERDICT_PATCH_FAILED = "patch-failed"

HUNK_HEADER = re.compile(r"^@@ -(?P<orig_start>\d+)(?:,(?P<orig_len>\d+))? \+\d+(?:,\d+)? @@")

IGNORED_COPY_PATTERNS = ("__pycache__", ".git", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox", ".venv")

RunnerFunc = Callable[..., TestRun]


class PatchApplyError(Exception):
    """A unified diff hunk did not match the file it was generated from."""


def verify_fixes(
    project_path: Path,
    suggestions: list[FixSuggestion],
    baseline_failures: list[Failure],
    extra_args: list[str] | None = None,
    timeout: int = 120,
    runner: RunnerFunc | None = None,
) -> VerificationResult | None:
    """Apply ``suggestions`` to a temporary copy of the project and rerun pytest there.

    Returns ``None`` when there is nothing to verify. The original project is
    never modified.
    """
    if not suggestions:
        return None
    if runner is None:
        runner = run_pytest

    project_path = project_path.resolve()
    guardrails = _unique_keep_order(nodeid for suggestion in suggestions for nodeid in suggestion.guardrail_tests)

    with tempfile.TemporaryDirectory(prefix="agentic-testops-verify-") as temp_dir:
        workdir = Path(temp_dir) / project_path.name
        shutil.copytree(project_path, workdir, ignore=shutil.ignore_patterns(*IGNORED_COPY_PATTERNS))

        try:
            applied_files = _apply_suggestions(workdir, suggestions)
        except PatchApplyError as exc:
            return VerificationResult(
                verdict=VERDICT_PATCH_FAILED,
                applied_suggestions=[],
                guardrail_tests=guardrails,
                notes=[f"Patch application failed: {exc}"],
            )

        guardrail_run = None
        if guardrails:
            local_guardrails = [_localize_nodeid(workdir, nodeid) for nodeid in guardrails]
            guardrail_args = [*(extra_args or []), *local_guardrails]
            guardrail_run = runner(workdir, extra_args=guardrail_args, timeout=timeout)
            if not guardrail_run.passed:
                return VerificationResult(
                    verdict=VERDICT_FIX_INEFFECTIVE,
                    applied_suggestions=applied_files,
                    guardrail_tests=guardrails,
                    guardrail_run=guardrail_run,
                    notes=["At least one guardrail test still fails after applying the suggested patches."],
                )

        full_run = runner(workdir, extra_args=list(extra_args or []), timeout=timeout)
        new_failures = _new_failure_nodeids(full_run, baseline_failures)
        if new_failures:
            return VerificationResult(
                verdict=VERDICT_FIX_REGRESSED,
                applied_suggestions=applied_files,
                guardrail_tests=guardrails,
                guardrail_run=guardrail_run,
                full_run=full_run,
                new_failures=new_failures,
                notes=["The full suite shows failures that were not present before the patches."],
            )

        notes = []
        if not full_run.passed:
            notes.append(
                "Remaining failures were already present in the baseline run and are not "
                "covered by the applied suggestions."
            )
        return VerificationResult(
            verdict=VERDICT_FIX_CONFIRMED,
            applied_suggestions=applied_files,
            guardrail_tests=guardrails,
            guardrail_run=guardrail_run,
            full_run=full_run,
            notes=notes,
        )


def apply_unified_diff(original_lines: list[str], diff_text: str) -> list[str]:
    """Apply a unified diff (as produced by ``fixer._make_diff``) to ``original_lines``.

    Raises :class:`PatchApplyError` when a hunk does not match the input,
    which keeps verification honest instead of silently producing a tree that
    differs from the reviewed suggestion.
    """
    result: list[str] = []
    cursor = 0
    in_hunk = False

    for raw_line in diff_text.splitlines():
        if raw_line.startswith(("--- ", "+++ ")):
            in_hunk = False
            continue
        header = HUNK_HEADER.match(raw_line)
        if header:
            orig_start = int(header.group("orig_start"))
            orig_len = int(header.group("orig_len")) if header.group("orig_len") is not None else 1
            # For zero-length source ranges the header names the line *before*
            # the insertion point, so the hunk body starts after that line.
            hunk_start = orig_start if orig_len == 0 else orig_start - 1
            if hunk_start < cursor or hunk_start > len(original_lines):
                raise PatchApplyError(f"Hunk start {orig_start} is out of order or beyond the file end.")
            result.extend(original_lines[cursor:hunk_start])
            cursor = hunk_start
            in_hunk = True
            continue
        if not in_hunk:
            continue
        tag, text = raw_line[:1], raw_line[1:]
        if tag in {" ", "-"}:
            if cursor >= len(original_lines) or original_lines[cursor] != text:
                found = original_lines[cursor] if cursor < len(original_lines) else "<end of file>"
                raise PatchApplyError(f"Expected line {cursor + 1} to be {text!r}, found {found!r}.")
            if tag == " ":
                result.append(text)
            cursor += 1
        elif tag == "+":
            result.append(text)
        else:
            raise PatchApplyError(f"Unrecognized diff line: {raw_line!r}")

    result.extend(original_lines[cursor:])
    return result


def _apply_suggestions(workdir: Path, suggestions: list[FixSuggestion]) -> list[str]:
    """Apply each suggestion in order, tracking evolving per-file state.

    Suggestions for the same file are generated against the previous
    suggestion's output (see ``fixer.suggest_fixes``), so sequential
    application reproduces exactly the reviewed diffs.
    """
    file_states: dict[str, list[str]] = {}
    applied: list[str] = []
    for suggestion in suggestions:
        target = workdir / suggestion.target_file
        if not _is_relative_to(target.resolve(), workdir.resolve()):
            raise PatchApplyError(f"Suggestion target escapes the project: {suggestion.target_file}")
        if not target.exists():
            raise PatchApplyError(f"Suggestion target does not exist: {suggestion.target_file}")
        lines = file_states.get(suggestion.target_file)
        if lines is None:
            lines = target.read_text(encoding="utf-8").splitlines()
        changed = apply_unified_diff(lines, suggestion.diff)
        target.write_text("\n".join(changed) + "\n", encoding="utf-8")
        file_states[suggestion.target_file] = changed
        applied.append(suggestion.failure_nodeid)
    return applied


def _localize_nodeid(workdir: Path, nodeid: str) -> str:
    """Rewrite a nodeid so its file part resolves inside the temporary copy.

    Depending on the discovered pytest rootdir, parsed nodeids may carry an
    absolute path or a repository-relative prefix (``examples/project/...``)
    that does not exist inside the copied project tree. Leading path segments
    are stripped until the file resolves; the original ID is kept as a last
    resort.
    """
    path_part, separator, rest = nodeid.partition("::")
    candidate = Path(path_part)
    if not candidate.is_absolute() and (workdir / candidate).exists():
        return nodeid
    parts = candidate.parts
    start = 1 if candidate.is_absolute() else 0
    for index in range(start, len(parts)):
        suffix = Path(*parts[index:])
        if (workdir / suffix).exists():
            return f"{suffix.as_posix()}{separator}{rest}"
    return nodeid


def _new_failure_nodeids(full_run: TestRun, baseline_failures: list[Failure]) -> list[str]:
    if full_run.passed:
        return []
    baseline_nodeids = [failure.nodeid for failure in baseline_failures]
    current = parse_failures(full_run)
    return [
        failure.nodeid
        for failure in current
        if not any(_nodeids_match(failure.nodeid, baseline) for baseline in baseline_nodeids)
    ]


def _unique_keep_order(items: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item)
    return list(seen)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
