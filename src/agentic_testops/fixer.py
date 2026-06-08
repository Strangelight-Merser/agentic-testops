from __future__ import annotations

import difflib
import re
from pathlib import Path

from .models import Diagnosis, FixSuggestion, PatchProposal

UNEXPECTED_KEYWORD = re.compile(r"(?P<name>\w+)\(\) got an unexpected keyword argument '(?P<keyword>\w+)'")
KEY_ERROR = re.compile(r"KeyError: ['\"](?P<key>\w+)['\"]")
RETURN_DIVISION = re.compile(r"^(?P<indent>\s*)return\s+(?P<numerator>.+?)\s*/\s*(?P<divisor>[A-Za-z_]\w*)\s*$")
RETURN_DIVISION_BY_LEN = re.compile(
    r"^(?P<indent>\s*)return\s+(?P<numerator>.+?)\s*/\s*len\((?P<name>[A-Za-z_]\w*)\)\s*$"
)


def suggest_fixes(
    project_path: Path,
    diagnoses: list[Diagnosis],
    patch_proposals: list[PatchProposal],
) -> list[FixSuggestion]:
    project_path = project_path.resolve()
    proposal_by_nodeid = {proposal.failure_nodeid: proposal for proposal in patch_proposals}
    file_states: dict[str, list[str]] = {}
    suggestions: list[FixSuggestion] = []
    for diagnosis in diagnoses:
        proposal = proposal_by_nodeid.get(diagnosis.failure.nodeid)
        suggestion, changed = _suggest_fix(project_path, diagnosis, proposal, file_states)
        if suggestion:
            suggestions.append(suggestion)
            file_states[suggestion.target_file] = changed
    return suggestions


def render_fix_suggestions_patch(suggestions: list[FixSuggestion]) -> str:
    if not suggestions:
        return "# No conservative fix suggestions were generated.\n"
    return "\n\n".join(suggestion.diff.rstrip("\n") for suggestion in suggestions) + "\n"


def _suggest_fix(
    project_path: Path,
    diagnosis: Diagnosis,
    proposal: PatchProposal | None,
    file_states: dict[str, list[str]],
) -> tuple[FixSuggestion | None, list[str]]:
    target_file = proposal.target_file if proposal else diagnosis.failure.file_path
    if not target_file:
        return None, []

    target_path = (project_path / target_file).resolve()
    if not _is_relative_to(target_path, project_path) or not target_path.exists():
        return None, []

    lines = file_states.get(target_file)
    if lines is None:
        lines = target_path.read_text(encoding="utf-8").splitlines()
    changed: list[str] | None = None
    title = ""
    explanation = ""

    if diagnosis.category == "input-validation" and diagnosis.failure.error_type == "ZeroDivisionError":
        changed, title, explanation = _suggest_zero_division_guard(lines, diagnosis)
    elif diagnosis.category == "api-contract":
        changed, title, explanation = _suggest_unexpected_keyword_support(lines, diagnosis)
    elif diagnosis.category == "data-shape" and diagnosis.failure.error_type == "KeyError":
        changed, title, explanation = _suggest_key_error_field_alignment(lines, diagnosis)
    elif diagnosis.category == "data-shape" and diagnosis.failure.error_type == "IndexError":
        changed, title, explanation = _suggest_empty_sequence_guard(lines, diagnosis)

    if not changed or changed == lines:
        return None, lines

    diff = _make_diff(target_file, lines, changed)
    return (
        FixSuggestion(
            failure_nodeid=diagnosis.failure.nodeid,
            target_file=target_file,
            title=title,
            explanation=explanation,
            confidence=diagnosis.confidence,
            diff=diff,
            guardrail_tests=[diagnosis.failure.nodeid],
        ),
        changed,
    )


def _suggest_zero_division_guard(lines: list[str], diagnosis: Diagnosis) -> tuple[list[str] | None, str, str]:
    for index in _candidate_indexes(diagnosis.failure.line_number, lines):
        line = lines[index]
        by_len = RETURN_DIVISION_BY_LEN.match(line)
        if by_len:
            indent = by_len.group("indent")
            name = by_len.group("name")
            changed = [*lines[:index], f"{indent}if not {name}:", f"{indent}    return 0", *lines[index:]]
            return (
                changed,
                f"Return 0 before dividing by empty `{name}`.",
                "The failing traceback shows division by `len(...)`; the guard handles the empty input before the unsafe operation.",
            )

        division = RETURN_DIVISION.match(line)
        if division:
            indent = division.group("indent")
            divisor = division.group("divisor")
            changed = [
                *lines[:index],
                f"{indent}if {divisor} == 0:",
                f"{indent}    raise ValueError(\"division by zero\")",
                *lines[index:],
            ]
            return (
                changed,
                f"Validate `{divisor}` before division.",
                "The failing test expects invalid division input to be rejected with a domain error instead of leaking ZeroDivisionError.",
            )

    return None, "", ""


def _suggest_unexpected_keyword_support(lines: list[str], diagnosis: Diagnosis) -> tuple[list[str] | None, str, str]:
    match = UNEXPECTED_KEYWORD.search(diagnosis.failure.headline)
    if not match:
        return None, "", ""

    function_name = match.group("name")
    keyword = match.group("keyword")
    def_index = _find_function_def(lines, function_name)
    if def_index is None:
        return None, "", ""

    def_line = lines[def_index]
    if keyword in def_line:
        return None, "", ""

    prefix, suffix = def_line.rsplit(")", 1)
    separator = "" if prefix.rstrip().endswith("(") else ", "
    changed = lines.copy()
    changed[def_index] = f"{prefix}{separator}{keyword}=None){suffix}"

    return_index = _find_return_dict_line(changed, def_index)
    if return_index is not None and keyword not in changed[return_index]:
        changed[return_index] = changed[return_index].replace("}", f", \"{keyword}\": {keyword}}}", 1)

    return (
        changed,
        f"Accept optional `{keyword}` metadata in `{function_name}`.",
        "The test calls the public function with a keyword argument that the implementation currently rejects.",
    )


def _suggest_key_error_field_alignment(lines: list[str], diagnosis: Diagnosis) -> tuple[list[str] | None, str, str]:
    match = KEY_ERROR.search(diagnosis.failure.headline)
    if not match or "done" not in diagnosis.failure.detail:
        return None, "", ""

    missing_key = match.group("key")
    for index in _candidate_indexes(diagnosis.failure.line_number, lines):
        if f'["{missing_key}"]' not in lines[index]:
            continue
        changed = lines.copy()
        changed[index] = changed[index].replace(f'["{missing_key}"]', '["done"]')
        return (
            changed,
            f"Read the observed `done` field instead of missing `{missing_key}`.",
            "The failing fixture uses `done`; aligning the accessed key removes the shape mismatch exposed by the test.",
        )
    return None, "", ""


def _suggest_empty_sequence_guard(lines: list[str], diagnosis: Diagnosis) -> tuple[list[str] | None, str, str]:
    for index in _candidate_indexes(diagnosis.failure.line_number, lines):
        line = lines[index]
        if "[0]" not in line:
            continue

        indent = line[: len(line) - len(line.lstrip())]
        sequence_name = _sequence_name_from_index_access(line)
        if not sequence_name:
            continue

        changed = [*lines[:index], f"{indent}if not {sequence_name}:", f"{indent}    return None", *lines[index:]]
        return (
            changed,
            f"Return `None` when `{sequence_name}` is empty.",
            "The failing test documents the empty-backlog behavior, so the guard handles the boundary before index access.",
        )
    return None, "", ""


def _candidate_indexes(line_number: int | None, lines: list[str]) -> list[int]:
    indexes = list(range(len(lines)))
    if line_number is None:
        return indexes
    preferred = line_number - 1
    if 0 <= preferred < len(lines):
        after = [index for index in indexes if index > preferred]
        before = [index for index in indexes if index < preferred]
        return [preferred, *after, *before]
    return indexes


def _find_function_def(lines: list[str], function_name: str) -> int | None:
    pattern = re.compile(rf"^\s*def\s+{re.escape(function_name)}\s*\(")
    for index, line in enumerate(lines):
        if pattern.match(line):
            return index
    return None


def _find_return_dict_line(lines: list[str], def_index: int) -> int | None:
    def_indent = len(lines[def_index]) - len(lines[def_index].lstrip())
    for index in range(def_index + 1, len(lines)):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= def_indent and stripped.startswith("def "):
            return None
        if stripped.startswith("return {") and stripped.endswith("}"):
            return index
    return None


def _sequence_name_from_index_access(line: str) -> str | None:
    match = re.search(r"(?P<name>[A-Za-z_]\w*)\[0\]", line)
    return match.group("name") if match else None


def _make_diff(target_file: str, original: list[str], changed: list[str]) -> str:
    diff = difflib.unified_diff(
        [f"{line}\n" for line in original],
        [f"{line}\n" for line in changed],
        fromfile=f"a/{target_file}",
        tofile=f"b/{target_file}",
        n=0,
    )
    raw = "".join(diff).rstrip()
    lines = [" " if line == "" else line for line in raw.splitlines()]
    return "\n".join(lines)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
