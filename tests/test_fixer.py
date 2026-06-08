from pathlib import Path
import shutil
import subprocess

import pytest

from agentic_testops.fixer import render_fix_suggestions_patch, suggest_fixes
from agentic_testops.models import Diagnosis, Failure, PatchProposal


def _diagnosis(
    *,
    nodeid: str = "test_app.py::test_case",
    category: str,
    error_type: str,
    headline: str,
    file_path: str,
    line_number: int,
    detail: str = "",
) -> Diagnosis:
    return Diagnosis(
        failure=Failure(
            nodeid=nodeid,
            headline=headline,
            file_path=file_path,
            line_number=line_number,
            error_type=error_type,
            detail=detail,
        ),
        category=category,
        confidence="medium",
        summary="test diagnosis",
    )


def _proposal(diagnosis: Diagnosis) -> PatchProposal:
    return PatchProposal(
        failure_nodeid=diagnosis.failure.nodeid,
        target_file=diagnosis.failure.file_path,
        target_line=diagnosis.failure.line_number,
        action="test action",
        rationale="test rationale",
        confidence="medium",
        guardrail_tests=[diagnosis.failure.nodeid],
    )


def test_suggest_zero_division_guard_without_mutating_file(tmp_path: Path) -> None:
    target = tmp_path / "calculator.py"
    original = "def divide(a, b):\n    return a / b\n"
    target.write_text(original, encoding="utf-8")
    diagnosis = _diagnosis(
        category="input-validation",
        error_type="ZeroDivisionError",
        headline="ZeroDivisionError: division by zero",
        file_path="calculator.py",
        line_number=2,
    )

    suggestions = suggest_fixes(tmp_path, [diagnosis], [_proposal(diagnosis)])

    assert "if b == 0:" in suggestions[0].diff
    assert "raise ValueError" in suggestions[0].diff
    assert "\n\n+" not in suggestions[0].diff
    assert target.read_text(encoding="utf-8") == original


def test_suggest_empty_len_guard(tmp_path: Path) -> None:
    (tmp_path / "calculator.py").write_text("def average(values):\n    return sum(values) / len(values)\n", encoding="utf-8")
    diagnosis = _diagnosis(
        category="input-validation",
        error_type="ZeroDivisionError",
        headline="ZeroDivisionError: division by zero",
        file_path="calculator.py",
        line_number=2,
    )

    suggestions = suggest_fixes(tmp_path, [diagnosis], [_proposal(diagnosis)])

    assert "if not values:" in suggestions[0].diff
    assert "return 0" in suggestions[0].diff


def test_suggest_unexpected_keyword_support(tmp_path: Path) -> None:
    (tmp_path / "task_tracker.py").write_text(
        "def create_task(title):\n    return {\"title\": title, \"done\": False}\n",
        encoding="utf-8",
    )
    diagnosis = _diagnosis(
        category="api-contract",
        error_type="TypeError",
        headline="TypeError: create_task() got an unexpected keyword argument 'priority'",
        file_path="task_tracker.py",
        line_number=1,
    )

    suggestions = suggest_fixes(tmp_path, [diagnosis], [_proposal(diagnosis)])

    assert "def create_task(title, priority=None):" in suggestions[0].diff
    assert '"priority": priority' in suggestions[0].diff


def test_suggest_done_field_for_key_error(tmp_path: Path) -> None:
    (tmp_path / "task_tracker.py").write_text(
        "def completion_rate(tasks):\n    return sum(1 for task in tasks if task[\"completed\"])\n",
        encoding="utf-8",
    )
    diagnosis = _diagnosis(
        category="data-shape",
        error_type="KeyError",
        headline="KeyError: 'completed'",
        file_path="task_tracker.py",
        line_number=2,
        detail='{"done": true}',
    )

    suggestions = suggest_fixes(tmp_path, [diagnosis], [_proposal(diagnosis)])

    assert 'task["done"]' in suggestions[0].diff


def test_suggest_empty_sequence_guard(tmp_path: Path) -> None:
    (tmp_path / "task_tracker.py").write_text(
        "def next_task(tasks):\n    sorted_tasks = sorted(tasks)\n    return sorted_tasks[0]\n",
        encoding="utf-8",
    )
    diagnosis = _diagnosis(
        category="data-shape",
        error_type="IndexError",
        headline="IndexError: list index out of range",
        file_path="task_tracker.py",
        line_number=3,
    )

    suggestions = suggest_fixes(tmp_path, [diagnosis], [_proposal(diagnosis)])

    assert "if not sorted_tasks:" in suggestions[0].diff
    assert "return None" in suggestions[0].diff


def test_render_fix_suggestions_patch_empty() -> None:
    assert "No conservative fix suggestions" in render_fix_suggestions_patch([])


def test_render_fix_suggestions_patch_is_plain_unified_diff(tmp_path: Path) -> None:
    target = tmp_path / "calculator.py"
    target.write_text("def divide(a, b):\n    return a / b\n\n\ndef other():\n    return 1\n", encoding="utf-8")
    diagnosis = _diagnosis(
        category="input-validation",
        error_type="ZeroDivisionError",
        headline="ZeroDivisionError: division by zero",
        file_path="calculator.py",
        line_number=2,
    )

    patch_text = render_fix_suggestions_patch(suggest_fixes(tmp_path, [diagnosis], [_proposal(diagnosis)]))

    assert patch_text.startswith("--- a/calculator.py")
    assert "# test_app.py::test_case" not in patch_text
    assert "@@" in patch_text


def test_rendered_patch_applies_multiple_suggestions_for_same_file(tmp_path: Path) -> None:
    if not shutil.which("patch"):
        pytest.skip("patch command is not available")

    target = tmp_path / "calculator.py"
    target.write_text(
        "def divide(a, b):\n    return a / b\n\n\ndef average(values):\n    return sum(values) / len(values)\n",
        encoding="utf-8",
    )
    divide = _diagnosis(
        nodeid="test_calculator.py::test_divide_rejects_zero",
        category="input-validation",
        error_type="ZeroDivisionError",
        headline="ZeroDivisionError: division by zero",
        file_path="calculator.py",
        line_number=2,
    )
    average = _diagnosis(
        nodeid="test_calculator.py::test_average_empty_list_returns_zero",
        category="input-validation",
        error_type="ZeroDivisionError",
        headline="ZeroDivisionError: division by zero",
        file_path="calculator.py",
        line_number=6,
    )
    patch_path = tmp_path / "fixes.patch"
    patch_path.write_text(
        render_fix_suggestions_patch(suggest_fixes(tmp_path, [divide, average], [_proposal(divide), _proposal(average)])),
        encoding="utf-8",
    )

    subprocess.run(["patch", "-p1", "-i", str(patch_path)], cwd=tmp_path, check=True, capture_output=True, text=True)

    fixed = target.read_text(encoding="utf-8")
    assert "if b == 0:" in fixed
    assert "if not values:" in fixed
