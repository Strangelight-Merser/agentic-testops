from pathlib import Path
import shutil
import subprocess
import sys

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


def test_suggest_unexpected_keyword_support_for_multiline_signature(tmp_path: Path) -> None:
    target = tmp_path / "task_tracker.py"
    original = (
        "def create_task(\n"
        "    title,\n"
        "):\n"
        "    return {\"title\": title, \"done\": False}\n"
    )
    target.write_text(original, encoding="utf-8")
    diagnosis = _diagnosis(
        category="api-contract",
        error_type="TypeError",
        headline="TypeError: create_task() got an unexpected keyword argument 'priority'",
        file_path="task_tracker.py",
        line_number=1,
    )

    suggestions = suggest_fixes(tmp_path, [diagnosis], [_proposal(diagnosis)])

    assert "priority=None," in suggestions[0].diff
    assert '"priority": priority' in suggestions[0].diff
    assert target.read_text(encoding="utf-8") == original


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


def test_suggest_missing_config_default(tmp_path: Path) -> None:
    (tmp_path / "service_health.py").write_text(
        "from pathlib import Path\n\n\n"
        "def load_config(path):\n"
        "    config_path = Path(path)\n"
        "    if not config_path.exists():\n"
        "        raise FileNotFoundError(f\"Missing config file: {config_path}\")\n"
        "    return {\"raw\": config_path.read_text()}\n",
        encoding="utf-8",
    )
    diagnosis = _diagnosis(
        category="filesystem-boundary",
        error_type="FileNotFoundError",
        headline="FileNotFoundError: Missing config file: missing.env",
        file_path="service_health.py",
        line_number=7,
        detail='assert load_config("missing.env") == {"raw": ""}',
    )

    suggestions = suggest_fixes(tmp_path, [diagnosis], [_proposal(diagnosis)])

    assert 'return {"raw": ""}' in suggestions[0].diff


def test_suggest_dict_attribute_access(tmp_path: Path) -> None:
    (tmp_path / "service_health.py").write_text(
        "def display_name(user):\n    return user.name.title()\n",
        encoding="utf-8",
    )
    diagnosis = _diagnosis(
        category="object-interface",
        error_type="AttributeError",
        headline="AttributeError: 'dict' object has no attribute 'name'",
        file_path="service_health.py",
        line_number=2,
    )

    suggestions = suggest_fixes(tmp_path, [diagnosis], [_proposal(diagnosis)])

    assert 'user["name"].title()' in suggestions[0].diff


def test_suggest_missing_subtotal(tmp_path: Path) -> None:
    (tmp_path / "service_health.py").write_text(
        "def invoice_total(items):\n    tax_rate = 0.08\n    return subtotal + (subtotal * tax_rate)\n",
        encoding="utf-8",
    )
    diagnosis = _diagnosis(
        category="symbol-resolution",
        error_type="NameError",
        headline="NameError: name 'subtotal' is not defined",
        file_path="service_health.py",
        line_number=3,
    )

    suggestions = suggest_fixes(tmp_path, [diagnosis], [_proposal(diagnosis)])

    assert 'subtotal = sum(item["amount"] for item in items)' in suggestions[0].diff


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


def test_rendered_patch_fixes_service_health_example(tmp_path: Path) -> None:
    if not shutil.which("patch"):
        pytest.skip("patch command is not available")

    (tmp_path / "service_health.py").write_text(
        "from pathlib import Path\n\n\n"
        "def load_config(path):\n"
        "    config_path = Path(path)\n"
        "    if not config_path.exists():\n"
        "        raise FileNotFoundError(f\"Missing config file: {config_path}\")\n"
        "    text = config_path.read_text(encoding=\"utf-8\")\n"
        "    return {\"raw\": text}\n\n\n"
        "def display_name(user):\n"
        "    return user.name.title()\n\n\n"
        "def invoice_total(items):\n"
        "    tax_rate = 0.08\n"
        "    return subtotal + (subtotal * tax_rate)\n",
        encoding="utf-8",
    )
    (tmp_path / "test_service_health.py").write_text(
        "from service_health import display_name, invoice_total, load_config\n\n\n"
        "def test_load_config_handles_missing_file():\n"
        "    assert load_config(\"missing.env\") == {\"raw\": \"\"}\n\n\n"
        "def test_display_name_accepts_dict_user():\n"
        "    assert display_name({\"name\": \"ada lovelace\"}) == \"Ada Lovelace\"\n\n\n"
        "def test_invoice_total_sums_items_with_tax():\n"
        "    assert invoice_total([{\"amount\": 10.0}, {\"amount\": 5.0}]) == 16.2\n",
        encoding="utf-8",
    )
    diagnoses = [
        _diagnosis(
            nodeid="test_service_health.py::test_load_config_handles_missing_file",
            category="filesystem-boundary",
            error_type="FileNotFoundError",
            headline="FileNotFoundError: Missing config file: missing.env",
            file_path="service_health.py",
            line_number=7,
            detail='assert load_config("missing.env") == {"raw": ""}',
        ),
        _diagnosis(
            nodeid="test_service_health.py::test_display_name_accepts_dict_user",
            category="object-interface",
            error_type="AttributeError",
            headline="AttributeError: 'dict' object has no attribute 'name'",
            file_path="service_health.py",
            line_number=13,
        ),
        _diagnosis(
            nodeid="test_service_health.py::test_invoice_total_sums_items_with_tax",
            category="symbol-resolution",
            error_type="NameError",
            headline="NameError: name 'subtotal' is not defined",
            file_path="service_health.py",
            line_number=17,
        ),
    ]
    patch_path = tmp_path / "fixes.patch"
    patch_path.write_text(
        render_fix_suggestions_patch(suggest_fixes(tmp_path, diagnoses, [_proposal(diagnosis) for diagnosis in diagnoses])),
        encoding="utf-8",
    )

    subprocess.run(["patch", "-p1", "-i", str(patch_path)], cwd=tmp_path, check=True, capture_output=True, text=True)
    completed = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=tmp_path, check=True, capture_output=True, text=True)

    assert "3 passed" in completed.stdout


def test_sample_service_health_patch_applies_to_documented_example(tmp_path: Path) -> None:
    if not shutil.which("patch"):
        pytest.skip("patch command is not available")

    demo = tmp_path / "service_health"
    demo.mkdir()
    shutil.copy(Path("examples/service_health/service_health.py"), demo / "service_health.py")
    shutil.copy(Path("examples/service_health/test_service_health.py"), demo / "test_service_health.py")

    subprocess.run(
        ["patch", "-p1", "-i", str(Path.cwd() / "docs/sample-service-health-fixes.patch")],
        cwd=demo,
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=demo, check=True, capture_output=True, text=True)

    assert "3 passed" in completed.stdout
