from __future__ import annotations

import ast
import re
from pathlib import Path

from .models import Diagnosis, PatchProposal

UNEXPECTED_KEYWORD = re.compile(r"(?P<name>\w+)\(\) got an unexpected keyword argument")
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site-packages",
    "venv",
}


def propose_patches(diagnoses: list[Diagnosis], project_path: Path | None = None) -> list[PatchProposal]:
    return [_proposal_for(diagnosis, project_path) for diagnosis in diagnoses]


def _proposal_for(diagnosis: Diagnosis, project_path: Path | None) -> PatchProposal:
    failure = diagnosis.failure
    target_file = failure.file_path
    target_line = failure.line_number
    guardrails = [failure.nodeid]

    if diagnosis.category == "input-validation":
        return PatchProposal(
            failure_nodeid=failure.nodeid,
            target_file=target_file,
            target_line=target_line,
            action="Add explicit validation for the failing boundary input before the unsafe operation.",
            rationale="The traceback shows an invalid or boundary value reaching implementation code without a contract check.",
            confidence=diagnosis.confidence,
            guardrail_tests=guardrails,
        )

    if diagnosis.category == "dependency-or-import":
        return PatchProposal(
            failure_nodeid=failure.nodeid,
            target_file=target_file,
            target_line=target_line,
            action="Fix the import boundary by adding the missing dependency or correcting the local package path.",
            rationale="Import failures block test execution before behavior can be validated.",
            confidence=diagnosis.confidence,
            guardrail_tests=guardrails,
        )

    if diagnosis.category == "api-contract":
        located = _locate_api_contract_target(diagnosis, project_path)
        if located:
            target_file, target_line = located
        return PatchProposal(
            failure_nodeid=failure.nodeid,
            target_file=target_file,
            target_line=target_line,
            action="Align the failing call and callee signature, preserving compatibility if the function is public.",
            rationale="The error indicates callers and implementation disagree about accepted arguments or return shape.",
            confidence=diagnosis.confidence,
            guardrail_tests=guardrails,
        )

    if diagnosis.category == "data-shape":
        return PatchProposal(
            failure_nodeid=failure.nodeid,
            target_file=target_file,
            target_line=target_line,
            action="Normalize or validate the data shape before reading required keys or indexes.",
            rationale="The failing code attempted to read data that the test demonstrates may be absent or malformed.",
            confidence=diagnosis.confidence,
            guardrail_tests=guardrails,
        )

    if diagnosis.category == "filesystem-boundary":
        return PatchProposal(
            failure_nodeid=failure.nodeid,
            target_file=target_file,
            target_line=target_line,
            action="Make the file boundary explicit by validating the path, creating required fixtures, or handling the missing path case.",
            rationale="The traceback shows runtime file access reaching a missing, inaccessible, or invalid path.",
            confidence=diagnosis.confidence,
            guardrail_tests=guardrails,
        )

    if diagnosis.category == "object-interface":
        return PatchProposal(
            failure_nodeid=failure.nodeid,
            target_file=target_file,
            target_line=target_line,
            action="Align the expected object interface by normalizing the input shape or using the interface actually provided at runtime.",
            rationale="The failing access expects an attribute or method that the runtime object does not expose.",
            confidence=diagnosis.confidence,
            guardrail_tests=guardrails,
        )

    if diagnosis.category == "symbol-resolution":
        return PatchProposal(
            failure_nodeid=failure.nodeid,
            target_file=target_file,
            target_line=target_line,
            action="Resolve the missing symbol by importing, defining, passing, or consistently renaming it near the failing scope.",
            rationale="The code references a name that is unavailable when the failing path executes.",
            confidence=diagnosis.confidence,
            guardrail_tests=guardrails,
        )

    return PatchProposal(
        failure_nodeid=failure.nodeid,
        target_file=target_file,
        target_line=target_line,
        action="Inspect the nearest project frame and make the smallest code change that satisfies the failing test contract.",
        rationale="No higher-confidence domain rule matched this failure, so the proposal stays conservative.",
        confidence="low",
        guardrail_tests=guardrails,
    )


def _locate_api_contract_target(diagnosis: Diagnosis, project_path: Path | None) -> tuple[str, int] | None:
    if project_path is None:
        return None
    project_path = project_path.resolve()

    match = UNEXPECTED_KEYWORD.search(diagnosis.failure.headline)
    if not match:
        return None

    function_name = match.group("name")
    imported_target = _locate_imported_function_target(project_path, diagnosis.failure.file_path, function_name)
    if imported_target:
        return imported_target

    return _locate_function_in_project(project_path, function_name)


def _locate_imported_function_target(
    project_path: Path,
    failure_file: str | None,
    function_name: str,
) -> tuple[str, int] | None:
    if not failure_file:
        return None
    test_path = (project_path / failure_file).resolve()
    if not _is_relative_to(test_path, project_path) or not test_path.exists():
        return None

    try:
        tree = ast.parse(test_path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None

    for module_path in _imported_module_paths(tree, test_path, project_path, function_name):
        located = _locate_function_in_file(module_path, project_path, function_name)
        if located:
            return located
    return None


def _imported_module_paths(
    tree: ast.AST,
    test_path: Path,
    project_path: Path,
    function_name: str,
) -> list[Path]:
    paths: list[Path] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if not any(alias.name == function_name or alias.asname == function_name for alias in node.names):
            continue
        paths.extend(_module_file_candidates(node, test_path, project_path))
    return paths


def _module_file_candidates(node: ast.ImportFrom, test_path: Path, project_path: Path) -> list[Path]:
    module_parts = node.module.split(".") if node.module else []
    if node.level:
        root = test_path.parent
        for _ in range(node.level - 1):
            root = root.parent
        module_root = root.joinpath(*module_parts)
    else:
        module_root = project_path.joinpath(*module_parts)
    return [module_root.with_suffix(".py"), module_root / "__init__.py"]


def _locate_function_in_project(project_path: Path, function_name: str) -> tuple[str, int] | None:
    for path in sorted(project_path.rglob("*.py")):
        if _should_skip_path(path, project_path):
            continue
        located = _locate_function_in_file(path, project_path, function_name)
        if located:
            return located
    return None


def _locate_function_in_file(path: Path, project_path: Path, function_name: str) -> tuple[str, int] | None:
    path = path.resolve()
    if not _is_relative_to(path, project_path) or not path.exists() or _should_skip_path(path, project_path):
        return None
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return path.relative_to(project_path).as_posix(), node.lineno
    return None


def _should_skip_path(path: Path, project_path: Path) -> bool:
    relative_parts = path.relative_to(project_path).parts
    if any(part in IGNORED_DIRS for part in relative_parts):
        return True
    return path.name.startswith("test_") or "tests" in relative_parts


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
