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

    if diagnosis.category == "behavioral-regression":
        action = "Inspect the nearest project frame and make the smallest code change that satisfies the failing test contract."
        rationale = "An assertion failed, so the implementation behavior disagrees with the documented expectation."
        confidence = "low"
        located = _locate_assertion_target(diagnosis, project_path)
        if located:
            target_file, target_line = located
            action = "Adjust the implementation under test until the failing assertion's expected value holds."
            rationale = (
                "Traceback frames stay inside test code, so the target was localized by following the "
                "failing test module's imports to the implementation it exercises."
            )
            confidence = "medium"
        return PatchProposal(
            failure_nodeid=failure.nodeid,
            target_file=target_file,
            target_line=target_line,
            action=action,
            rationale=rationale,
            confidence=confidence,
            guardrail_tests=guardrails,
        )

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


def _locate_assertion_target(diagnosis: Diagnosis, project_path: Path | None) -> tuple[str, int] | None:
    """Localize assertion failures whose traceback never leaves test code.

    Output-comparison tests (``assert expected == actual``) raise inside the
    test or a shared helper, so frame-based localization blames test files.
    Instead, follow the failing test module's imports: find the functions the
    failing test actually calls, resolve which project module each call comes
    from, and point the patch target at that implementation definition.
    """
    if project_path is None:
        return None
    failure = diagnosis.failure
    if failure.file_path and not _is_test_like(failure.file_path):
        return None  # The frame already points at implementation code.

    project_path = project_path.resolve()
    test_file = failure.nodeid.split("::", 1)[0]
    if not test_file.endswith(".py"):
        return None
    test_path = (project_path / test_file).resolve()
    if not _is_relative_to(test_path, project_path) or not test_path.exists():
        return None
    try:
        tree = ast.parse(test_path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None

    test_name = failure.nodeid.rsplit("::", 1)[-1].split("[", 1)[0]
    test_node = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == test_name
        ),
        None,
    )
    if test_node is None:
        return None

    bindings = _import_bindings(tree, test_path, project_path)
    for binding, attribute in _called_refs(test_node):
        for module_path, imported_name in bindings.get(binding, []):
            function_name = attribute if imported_name is None else imported_name
            if attribute is not None and imported_name is not None:
                continue  # `binding.attr(...)` only makes sense for module bindings.
            if function_name is None:
                continue
            located = _locate_exported_function(module_path, project_path, function_name)
            if located and not _is_test_like(located[0]):
                return located
    return None


def _locate_exported_function(
    path: Path,
    project_path: Path,
    function_name: str,
    depth: int = 2,
    visited: set[Path] | None = None,
) -> tuple[str, int] | None:
    """Locate a function definition, following package re-exports.

    Packages often expose implementations through ``from .impl import *`` in
    ``__init__.py``; the definition then lives one module deeper than the
    import that the test names. Recursion is depth-limited and cycle-safe.
    """
    visited = visited if visited is not None else set()
    resolved = path.resolve()
    if resolved in visited:
        return None
    visited.add(resolved)

    located = _locate_function_in_file(path, project_path, function_name)
    if located:
        return located
    if depth <= 0 or not path.exists():
        return None
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        exported = {alias.asname or alias.name for alias in node.names}
        if function_name not in exported and "*" not in exported:
            continue
        for candidate in _module_file_candidates(node, path, project_path):
            located = _locate_exported_function(candidate, project_path, function_name, depth - 1, visited)
            if located:
                return located
    return None


def _called_refs(test_node: ast.AST) -> list[tuple[str, str | None]]:
    """Return ``(binding, attribute)`` pairs for calls inside the test, in order.

    ``func(...)`` yields ``("func", None)``; ``mod.func(...)`` yields
    ``("mod", "func")``.
    """
    refs: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for node in ast.walk(test_node):
        if not isinstance(node, ast.Call):
            continue
        ref: tuple[str, str | None] | None = None
        if isinstance(node.func, ast.Name):
            ref = (node.func.id, None)
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            ref = (node.func.value.id, node.func.attr)
        if ref and ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


def _import_bindings(
    tree: ast.AST,
    test_path: Path,
    project_path: Path,
) -> dict[str, list[tuple[Path, str | None]]]:
    """Map local names to ``(module_file_candidate, imported_name)`` pairs.

    ``imported_name`` is the original name for ``from mod import name`` and
    ``None`` when the binding refers to a module (``import mod`` or
    ``from pkg import mod``).
    """
    bindings: dict[str, list[tuple[Path, str | None]]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module_parts = node.module.split(".") if node.module else []
            if node.level:
                module_candidates = _module_file_candidates(node, test_path, project_path)
            else:
                module_candidates = _module_paths(project_path, module_parts)
            for alias in node.names:
                binding = alias.asname or alias.name
                entries = bindings.setdefault(binding, [])
                for candidate in module_candidates:
                    entries.append((candidate, alias.name))
                # `from pkg import mod` may bind a submodule used as `mod.func(...)`.
                for candidate in _module_paths(project_path, [*module_parts, alias.name]):
                    entries.append((candidate, None))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                binding = alias.asname or alias.name.split(".")[0]
                module_parts = alias.name.split(".") if alias.asname else [binding]
                entries = bindings.setdefault(binding, [])
                for candidate in _module_paths(project_path, module_parts):
                    entries.append((candidate, None))
    return bindings


def _module_paths(project_path: Path, module_parts: list[str]) -> list[Path]:
    candidates = []
    for root in (project_path, project_path / "src"):
        module_root = root.joinpath(*module_parts)
        candidates.extend([module_root.with_suffix(".py"), module_root / "__init__.py"])
    return candidates


def _is_test_like(relative_path: str) -> bool:
    parts = Path(relative_path).parts
    name = Path(relative_path).name
    if any(part in {"test", "tests", "testing"} for part in parts[:-1]):
        return True
    return name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


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
