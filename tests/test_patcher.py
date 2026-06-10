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


def test_propose_patch_prefers_imported_api_contract_target_over_global_match(tmp_path) -> None:
    (tmp_path / "aaa_wrong.py").write_text("def create_task(title):\n    return {'wrong': True}\n", encoding="utf-8")
    (tmp_path / "task_tracker.py").write_text("def create_task(title):\n    return {}\n", encoding="utf-8")
    (tmp_path / "test_task_tracker.py").write_text(
        "from task_tracker import create_task as make_task\n\n"
        "def test_case():\n"
        "    make_task('x', priority=1)\n",
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


def test_propose_patch_resolves_package_module_import(tmp_path) -> None:
    package = tmp_path / "todo"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "tasks.py").write_text("def create_task(title):\n    return {}\n", encoding="utf-8")
    (tmp_path / "test_task_tracker.py").write_text(
        "from todo.tasks import create_task\n\n"
        "def test_case():\n"
        "    create_task('x', priority=1)\n",
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

    assert proposals[0].target_file == "todo/tasks.py"
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


def test_propose_patch_for_filesystem_boundary_failure() -> None:
    failure = Failure(
        nodeid="test_config.py::test_load_missing_config",
        headline="FileNotFoundError: [Errno 2] No such file or directory: 'config.toml'",
        file_path="config_loader.py",
        line_number=7,
        error_type="FileNotFoundError",
    )
    diagnosis = Diagnosis(
        failure=failure,
        category="filesystem-boundary",
        confidence="medium",
        summary="Missing path.",
    )

    proposals = propose_patches([diagnosis])

    assert proposals[0].target_file == "config_loader.py"
    assert proposals[0].target_line == 7
    assert proposals[0].confidence == "medium"
    assert "file boundary" in proposals[0].action


def test_propose_patch_for_object_interface_failure() -> None:
    failure = Failure(
        nodeid="test_profiles.py::test_display_name_accepts_dict",
        headline="AttributeError: 'dict' object has no attribute 'name'",
        file_path="profiles.py",
        line_number=3,
        error_type="AttributeError",
    )
    diagnosis = Diagnosis(
        failure=failure,
        category="object-interface",
        confidence="medium",
        summary="Wrong object interface.",
    )

    proposals = propose_patches([diagnosis])

    assert proposals[0].target_file == "profiles.py"
    assert proposals[0].target_line == 3
    assert "object interface" in proposals[0].action


def test_propose_patch_for_symbol_resolution_failure() -> None:
    failure = Failure(
        nodeid="test_billing.py::test_total_includes_tax",
        headline="NameError: name 'subtotal' is not defined",
        file_path="billing.py",
        line_number=4,
        error_type="NameError",
    )
    diagnosis = Diagnosis(
        failure=failure,
        category="symbol-resolution",
        confidence="medium",
        summary="Missing symbol.",
    )

    proposals = propose_patches([diagnosis])

    assert proposals[0].target_file == "billing.py"
    assert proposals[0].target_line == 4
    assert "missing symbol" in proposals[0].action


def _assertion_diagnosis(nodeid: str, file_path: str | None) -> Diagnosis:
    failure = Failure(
        nodeid=nodeid,
        headline="AssertionError: assert 'a' == 'b'",
        file_path=file_path,
        line_number=10,
        error_type="AssertionError",
    )
    return Diagnosis(
        failure=failure,
        category="behavioral-regression",
        confidence="medium",
        summary="Assertion failed.",
    )


def test_assertion_target_follows_from_import_to_package(tmp_path) -> None:
    package = tmp_path / "renderlib"
    package.mkdir()
    (package / "__init__.py").write_text("def render(rows):\n    return ''\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "common.py").write_text("def assert_equal(a, b):\n    assert a == b\n", encoding="utf-8")
    (tests_dir / "test_render.py").write_text(
        "from renderlib import render\n"
        "from tests.common import assert_equal\n\n"
        "def test_render_table():\n"
        "    result = render([1])\n"
        "    assert_equal('expected', result)\n",
        encoding="utf-8",
    )
    diagnosis = _assertion_diagnosis("tests/test_render.py::test_render_table", "tests/common.py")

    proposals = propose_patches([diagnosis], project_path=tmp_path)

    assert proposals[0].target_file == "renderlib/__init__.py"
    assert proposals[0].target_line == 1
    assert proposals[0].confidence == "medium"
    assert "imports" in proposals[0].rationale


def test_assertion_target_resolves_module_attribute_calls(tmp_path) -> None:
    (tmp_path / "mylib.py").write_text("X = 1\n\ndef calc(n):\n    return n\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_calc.py").write_text(
        "import mylib\n\ndef test_calc():\n    assert mylib.calc(2) == 3\n",
        encoding="utf-8",
    )
    diagnosis = _assertion_diagnosis("tests/test_calc.py::test_calc", "tests/test_calc.py")

    proposals = propose_patches([diagnosis], project_path=tmp_path)

    assert proposals[0].target_file == "mylib.py"
    assert proposals[0].target_line == 3


def test_assertion_target_supports_src_layout(tmp_path) -> None:
    package = tmp_path / "src" / "mypkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("def go():\n    return 0\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_go.py").write_text(
        "from mypkg import go\n\ndef test_go():\n    assert go() == 1\n",
        encoding="utf-8",
    )
    diagnosis = _assertion_diagnosis("tests/test_go.py::test_go", "tests/test_go.py")

    proposals = propose_patches([diagnosis], project_path=tmp_path)

    assert proposals[0].target_file == "src/mypkg/__init__.py"
    assert proposals[0].target_line == 1


def test_assertion_target_keeps_implementation_frame_when_present(tmp_path) -> None:
    diagnosis = _assertion_diagnosis("tests/test_app.py::test_case", "app.py")

    proposals = propose_patches([diagnosis], project_path=tmp_path)

    assert proposals[0].target_file == "app.py"
    assert proposals[0].target_line == 10


def test_assertion_target_falls_back_when_unresolvable(tmp_path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_unknown.py").write_text(
        "def test_unknown():\n    assert helper() == 1\n",
        encoding="utf-8",
    )
    diagnosis = _assertion_diagnosis("tests/test_unknown.py::test_unknown", "tests/test_unknown.py")

    proposals = propose_patches([diagnosis], project_path=tmp_path)

    assert proposals[0].target_file == "tests/test_unknown.py"
    assert proposals[0].confidence == "low"


def test_assertion_target_never_points_at_test_helpers(tmp_path) -> None:
    tests_dir = tmp_path / "test"
    tests_dir.mkdir()
    (tests_dir / "common.py").write_text("def assert_equal(a, b):\n    assert a == b\n", encoding="utf-8")
    (tests_dir / "test_only_helpers.py").write_text(
        "from test.common import assert_equal\n\n"
        "def test_helpers_only():\n"
        "    assert_equal('a', 'b')\n",
        encoding="utf-8",
    )
    diagnosis = _assertion_diagnosis("test/test_only_helpers.py::test_helpers_only", "test/common.py")

    proposals = propose_patches([diagnosis], project_path=tmp_path)

    assert proposals[0].target_file == "test/common.py"
    assert proposals[0].confidence == "low"


def test_assertion_target_follows_package_reexports(tmp_path) -> None:
    package = tmp_path / "biglib"
    package.mkdir()
    (package / "__init__.py").write_text("from .core import *\n", encoding="utf-8")
    (package / "core.py").write_text("def combine(a, b):\n    return a + b\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_combine.py").write_text(
        "import biglib as bl\n\ndef test_combine():\n    assert bl.combine(1, 2) == 4\n",
        encoding="utf-8",
    )
    diagnosis = _assertion_diagnosis("tests/test_combine.py::test_combine", "tests/test_combine.py")

    proposals = propose_patches([diagnosis], project_path=tmp_path)

    assert proposals[0].target_file == "biglib/core.py"
    assert proposals[0].target_line == 1
