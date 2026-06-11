import shutil
import textwrap
from pathlib import Path

import pytest

from agentic_testops.diagnoser import diagnose_failures
from agentic_testops.fixer import suggest_fixes
from agentic_testops.models import Failure, FixSuggestion
from agentic_testops.parser import parse_failures
from agentic_testops.patcher import propose_patches
from agentic_testops.runner import run_pytest
from agentic_testops.verifier import (
    VERDICT_FIX_CONFIRMED,
    VERDICT_FIX_INEFFECTIVE,
    VERDICT_FIX_REGRESSED,
    VERDICT_PATCH_FAILED,
    PatchApplyError,
    _localize_nodeid,
    apply_unified_diff,
    verify_fixes,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _suggestion(target_file: str, diff: str, nodeid: str = "test_app.py::test_case") -> FixSuggestion:
    return FixSuggestion(
        failure_nodeid=nodeid,
        target_file=target_file,
        title="t",
        explanation="e",
        confidence="medium",
        diff=diff,
        guardrail_tests=[nodeid],
    )


def test_apply_unified_diff_insertion_and_replacement() -> None:
    original = ["def f(x):", "    return 1 / x"]
    diff = textwrap.dedent(
        """\
        --- a/app.py
        +++ b/app.py
        @@ -1,0 +2 @@
        +    # guard
        @@ -2 +3 @@
        -    return 1 / x
        +    return 0 if x == 0 else 1 / x"""
    )

    assert apply_unified_diff(original, diff) == [
        "def f(x):",
        "    # guard",
        "    return 0 if x == 0 else 1 / x",
    ]


def test_apply_unified_diff_rejects_mismatched_source() -> None:
    diff = textwrap.dedent(
        """\
        --- a/app.py
        +++ b/app.py
        @@ -1 +1 @@
        -expected line
        +replacement"""
    )

    with pytest.raises(PatchApplyError):
        apply_unified_diff(["different line"], diff)


def test_localize_nodeid_strips_foreign_prefixes(tmp_path: Path) -> None:
    (tmp_path / "test_app.py").write_text("", encoding="utf-8")

    relative = "test_app.py::test_case"
    repo_prefixed = "examples/project/test_app.py::test_case"
    absolute = "/somewhere/else/examples/project/test_app.py::test_case"
    unknown = "missing/test_other.py::test_case"

    assert _localize_nodeid(tmp_path, relative) == "test_app.py::test_case"
    assert _localize_nodeid(tmp_path, repo_prefixed) == "test_app.py::test_case"
    assert _localize_nodeid(tmp_path, absolute) == "test_app.py::test_case"
    assert _localize_nodeid(tmp_path, unknown) == unknown


def test_verify_fixes_returns_none_without_suggestions(tmp_path: Path) -> None:
    assert verify_fixes(tmp_path, [], baseline_failures=[]) is None


def test_verify_fixes_patch_failed_when_diff_does_not_apply(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("real content\n", encoding="utf-8")
    diff = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-other content\n+patched"
    runs: list[str] = []

    result = verify_fixes(
        tmp_path,
        [_suggestion("app.py", diff)],
        baseline_failures=[],
        runner=lambda *args, **kwargs: runs.append("called"),  # type: ignore[arg-type, return-value]
    )

    assert result is not None
    assert result.verdict == VERDICT_PATCH_FAILED
    assert runs == []  # no pytest run when the patch cannot be applied
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "real content\n"


def _write_min_project(tmp_path: Path, impl: str, tests: str) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text(textwrap.dedent(impl), encoding="utf-8")
    (project / "test_app.py").write_text(textwrap.dedent(tests), encoding="utf-8")
    return project


def test_verify_fixes_ineffective_when_guardrail_still_fails(tmp_path: Path) -> None:
    project = _write_min_project(
        tmp_path,
        impl="""\
        def add(a, b):
            return a - b
        """,
        tests="""\
        from app import add

        def test_add():
            assert add(2, 2) == 4
        """,
    )
    # A patch that applies cleanly but does not fix the bug.
    diff = "--- a/app.py\n+++ b/app.py\n@@ -1,0 +1 @@\n+# touched but not fixed"
    baseline = [Failure(nodeid="test_app.py::test_add", headline="AssertionError")]

    result = verify_fixes(project, [_suggestion("app.py", diff, "test_app.py::test_add")], baseline)

    assert result is not None
    assert result.verdict == VERDICT_FIX_INEFFECTIVE
    # Original project untouched.
    assert "# touched" not in (project / "app.py").read_text(encoding="utf-8")


def test_verify_fixes_regressed_when_new_failures_appear(tmp_path: Path) -> None:
    project = _write_min_project(
        tmp_path,
        impl="""\
        def add(a, b):
            return a - b

        def scale(a):
            return a * 2
        """,
        tests="""\
        from app import add, scale

        def test_add():
            assert add(2, 2) == 4

        def test_scale():
            assert scale(3) == 6
        """,
    )
    # Fixes add() but breaks scale().
    diff = (
        "--- a/app.py\n+++ b/app.py\n"
        "@@ -2 +2 @@\n-    return a - b\n+    return a + b\n"
        "@@ -5 +5 @@\n-    return a * 2\n+    return a * 3"
    )
    baseline = [Failure(nodeid="test_app.py::test_add", headline="AssertionError")]

    result = verify_fixes(project, [_suggestion("app.py", diff, "test_app.py::test_add")], baseline)

    assert result is not None
    assert result.verdict == VERDICT_FIX_REGRESSED
    assert any("test_scale" in nodeid for nodeid in result.new_failures)


def test_verify_fixes_confirms_service_health_pipeline(tmp_path: Path) -> None:
    project = tmp_path / "service_health"
    shutil.copytree(EXAMPLES / "service_health", project, ignore=shutil.ignore_patterns("__pycache__"))

    run = run_pytest(project, timeout=120)
    assert not run.passed
    failures = parse_failures(run)
    diagnoses = diagnose_failures(failures, run)
    proposals = propose_patches(diagnoses, project_path=project)
    suggestions = suggest_fixes(project, diagnoses, proposals)
    assert suggestions

    result = verify_fixes(project, suggestions, baseline_failures=failures, timeout=120)

    assert result is not None
    assert result.verdict == VERDICT_FIX_CONFIRMED
    assert result.full_run is not None and result.full_run.passed
    assert result.new_failures == []
    # The audited project itself was never modified.
    rerun = run_pytest(project, timeout=120)
    assert not rerun.passed
