from __future__ import annotations

import ast
import re
from pathlib import Path

from .models import Diagnosis, PatchProposal


UNEXPECTED_KEYWORD = re.compile(r"(?P<name>\w+)\(\) got an unexpected keyword argument")


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

    match = UNEXPECTED_KEYWORD.search(diagnosis.failure.headline)
    if not match:
        return None

    function_name = match.group("name")
    for path in sorted(project_path.rglob("*.py")):
        if path.name.startswith("test_") or "/tests/" in path.as_posix():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
                return path.relative_to(project_path).as_posix(), node.lineno
    return None
