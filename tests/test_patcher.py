from agentic_testops.models import Diagnosis, Failure
from agentic_testops.patcher import propose_patches


def test_propose_patch_for_input_validation_failure() -> None:
    failure = Failure(
        nodeid="test_calculator.py::test_divide_rejects_zero",
        headline="ZeroDivisionError: division by zero",
        file_path="calculator.py",
        line_number=2,
        error_type="ZeroDivisionError",
    )
    diagnosis = Diagnosis(
        failure=failure,
        category="input-validation",
        confidence="medium",
        summary="Boundary input is not validated.",
    )

    proposals = propose_patches([diagnosis])

    assert proposals[0].target_file == "calculator.py"
    assert proposals[0].target_line == 2
    assert "validation" in proposals[0].action


def test_propose_patch_locates_api_contract_implementation(tmp_path) -> None:
    (tmp_path / "task_tracker.py").write_text("def create_task(title):\n    return {}\n", encoding="utf-8")
    (tmp_path / "test_task_tracker.py").write_text(
        "from task_tracker import create_task\n\ndef test_case():\n    create_task('x', priority=1)\n",
        encoding="utf-8",
    )
    failure = Failure(
        nodeid="test_task_tracker.py::test_case",
        headline="TypeError: create_task() got an unexpected keyword argument 'priority'",
        file_path="test_task_tracker.py",
        line_number=4,
        error_type="TypeError",
    )
    diagnosis = Diagnosis(
        failure=failure,
        category="api-contract",
        confidence="medium",
        summary="Call and callee contract disagree.",
    )

    proposals = propose_patches([diagnosis], project_path=tmp_path)

    assert proposals[0].target_file == "task_tracker.py"
    assert proposals[0].target_line == 1


def test_propose_patch_skips_virtual_environment_matches(tmp_path) -> None:
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "task_tracker.py").write_text(
        "def create_task(title):\n    return {'wrong': True}\n",
        encoding="utf-8",
    )
    (tmp_path / "task_tracker.py").write_text("def create_task(title):\n    return {}\n", encoding="utf-8")
    failure = Failure(
        nodeid="test_task_tracker.py::test_case",
        headline="TypeError: create_task() got an unexpected keyword argument 'priority'",
        file_path="test_task_tracker.py",
        line_number=4,
        error_type="TypeError",
    )
    diagnosis = Diagnosis(
        failure=failure,
        category="api-contract",
        confidence="medium",
        summary="Call and callee contract disagree.",
    )

    proposals = propose_patches([diagnosis], project_path=tmp_path)

    assert proposals[0].target_file == "task_tracker.py"
