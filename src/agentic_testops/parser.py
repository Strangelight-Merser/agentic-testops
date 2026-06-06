from __future__ import annotations

import re

from .models import Failure, TestRun

FAILED_HEADER = re.compile(r"^_{3,}\s+(?P<nodeid>.+?)\s+_{3,}$")
FILE_LINE = re.compile(r"^(?P<path>[^:\n]+\.py):(?P<line>\d+):\s*(?P<etype>[A-Za-z_][\w.]*)(?::\s*(?P<detail>.*))?$")
TRACE_FRAME = re.compile(r"^(?P<path>[^:\n]+\.py):(?P<line>\d+):\s+in\s+\w+")
SHORT_SUMMARY = re.compile(r"^FAILED\s+(?P<nodeid>\S+)\s+-\s+(?P<headline>.+)$")


def parse_failures(run: TestRun) -> list[Failure]:
    output = "\n".join(part for part in [run.stdout, run.stderr] if part)
    if not output.strip() or run.passed:
        return []

    section_failures = _parse_failure_sections(output)
    summary_failures = _parse_short_summary(output)
    if section_failures:
        return _merge_summary_nodeids(section_failures, summary_failures)
    return summary_failures


def _parse_short_summary(output: str) -> list[Failure]:
    failures: list[Failure] = []
    for line in output.splitlines():
        match = SHORT_SUMMARY.match(line.strip())
        if not match:
            continue
        headline = match.group("headline").strip()
        error_type = headline.split(":", 1)[0] if ":" in headline else headline.split()[0]
        failures.append(
            Failure(
                nodeid=match.group("nodeid"),
                headline=headline,
                error_type=error_type,
                detail=headline,
            )
        )
    return failures


def _parse_failure_sections(output: str) -> list[Failure]:
    lines = output.splitlines()
    failures: list[Failure] = []
    current_nodeid: str | None = None
    current_block: list[str] = []

    def flush() -> None:
        if not current_nodeid:
            return
        failures.append(_failure_from_block(current_nodeid, current_block))

    for line in lines:
        header = FAILED_HEADER.match(line)
        if header:
            flush()
            current_nodeid = header.group("nodeid").strip()
            current_block = []
        elif current_nodeid and "short test summary info" in line:
            flush()
            current_nodeid = None
            current_block = []
        elif current_nodeid:
            current_block.append(line)
    flush()
    return failures


def _merge_summary_nodeids(section_failures: list[Failure], summary_failures: list[Failure]) -> list[Failure]:
    if not summary_failures:
        return section_failures

    merged: list[Failure] = []
    remaining = summary_failures.copy()
    for failure in section_failures:
        match = next((item for item in remaining if item.nodeid.endswith(f"::{failure.nodeid}")), None)
        if not match:
            merged.append(failure)
            continue
        remaining.remove(match)
        merged.append(
            Failure(
                nodeid=match.nodeid,
                headline=failure.headline,
                file_path=failure.file_path,
                line_number=failure.line_number,
                error_type=failure.error_type,
                detail=failure.detail,
            )
        )
    return merged


def _failure_from_block(nodeid: str, block: list[str]) -> Failure:
    headline = next((line.strip() for line in block if line.strip().startswith("E   ")), "Test failed")
    headline = headline.removeprefix("E   ").strip()
    file_path = None
    line_number = None
    error_type = _error_type_from_headline(headline)

    for line in reversed(block):
        frame = TRACE_FRAME.match(line.strip())
        if frame:
            file_path = frame.group("path")
            line_number = int(frame.group("line"))
            break
        match = FILE_LINE.match(line.strip())
        if match:
            file_path = match.group("path")
            line_number = int(match.group("line"))
            error_type = match.group("etype")
            if match.group("detail"):
                headline = f"{error_type}: {match.group('detail')}"
            break

    detail = "\n".join(block[-20:]).strip()
    return Failure(
        nodeid=nodeid,
        headline=headline,
        file_path=file_path,
        line_number=line_number,
        error_type=error_type,
        detail=detail,
    )


def _error_type_from_headline(headline: str) -> str | None:
    if not headline:
        return None
    first = headline.split(":", 1)[0] if ":" in headline else headline.split()[0]
    if first.endswith("Error") or first.endswith("Exception"):
        return first
    return first if first in {"AssertionError"} else None
