from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import PurePath

from .models import Failure, TestRun

FAILED_HEADER = re.compile(r"^_{3,}\s+(?P<nodeid>.+?)\s+_{3,}$")
FILE_LINE = re.compile(r"^(?P<path>[^:\n]+\.py):(?P<line>\d+):\s*(?P<etype>[A-Za-z_][\w.]*)(?::\s*(?P<detail>.*))?$")
TRACE_FRAME = re.compile(r"^(?P<path>[^:\n]+\.py):(?P<line>\d+):\s+in\s+\w+")
SHORT_SUMMARY = re.compile(r"^FAILED\s+(?P<nodeid>\S+)\s+-\s+(?P<headline>.+)$")


@dataclass(frozen=True)
class _Frame:
    path: str
    line_number: int
    error_type: str | None = None
    detail: str | None = None


def parse_failures(run: TestRun) -> list[Failure]:
    output = "\n".join(part for part in [run.stdout, run.stderr] if part)
    if run.passed:
        return []
    if not output.strip() and not run.junit_xml:
        return []

    junit_failures = _parse_junit_failures(run.junit_xml)
    if junit_failures:
        return junit_failures

    summary_failures = _parse_short_summary(output)
    section_failures = _parse_failure_sections(output)
    if section_failures:
        return _merge_summary_nodeids(section_failures, summary_failures)
    return summary_failures


def _parse_junit_failures(junit_xml: str) -> list[Failure]:
    if not junit_xml.strip():
        return []
    try:
        root = ET.fromstring(junit_xml)
    except ET.ParseError:
        return []

    failures: list[Failure] = []
    for testcase in root.iter("testcase"):
        child = testcase.find("failure")
        if child is None:
            child = testcase.find("error")
        if child is None:
            continue
        detail = (child.text or "").strip()
        headline = child.attrib.get("message") or _headline_from_detail(detail) or "Test failed"
        block = detail.splitlines()
        parsed = _failure_from_block(testcase.attrib.get("name", "testcase"), block)
        test_file_path = _first_trace_file(block)
        failures.append(
            Failure(
                nodeid=_nodeid_from_junit(testcase, test_file_path),
                headline=headline,
                file_path=parsed.file_path,
                line_number=parsed.line_number,
                error_type=_error_type_from_headline(headline) or parsed.error_type,
                detail=detail,
            )
        )
    return failures


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


def _headline_from_detail(detail: str) -> str | None:
    for line in detail.splitlines():
        line = line.strip()
        if line.startswith("E   "):
            return line.removeprefix("E   ").strip()
    return None


def _first_trace_file(block: list[str]) -> str | None:
    for line in block:
        frame = TRACE_FRAME.match(line.strip())
        if frame:
            return frame.group("path")
    return None


def _nodeid_from_junit(testcase: ET.Element, file_path: str | None = None) -> str:
    classname = testcase.attrib.get("classname", "")
    name = testcase.attrib.get("name", "testcase")
    class_name = _class_name_from_junit(classname)
    if file_path:
        if class_name:
            return f"{file_path}::{class_name}::{name}"
        return f"{file_path}::{name}"
    if not classname:
        return name

    parts = classname.split(".")
    if class_name and len(parts) >= 2:
        module_parts = parts[:-1]
        return f"{'/'.join(module_parts)}.py::{class_name}::{name}"
    return f"{'/'.join(parts)}.py::{name}"


def _class_name_from_junit(classname: str) -> str | None:
    if not classname:
        return None
    last = classname.split(".")[-1]
    return last if last.startswith("Test") else None


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
        match = next((item for item in remaining if _nodeid_matches_section(failure.nodeid, item.nodeid)), None)
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


def _nodeid_matches_section(section_nodeid: str, summary_nodeid: str) -> bool:
    if summary_nodeid.endswith(f"::{section_nodeid}"):
        return True
    if "::" not in summary_nodeid:
        return summary_nodeid == section_nodeid
    summary_tail = summary_nodeid.split("::", 1)[1].replace("::", ".")
    return summary_tail == section_nodeid or summary_tail.endswith(f".{section_nodeid}")


def _failure_from_block(nodeid: str, block: list[str]) -> Failure:
    headline = next((line.strip() for line in block if line.strip().startswith("E   ")), "Test failed")
    headline = headline.removeprefix("E   ").strip()
    file_path = None
    line_number = None
    error_type = _error_type_from_headline(headline)

    frame = _best_failure_frame(block)
    if frame:
        file_path = frame.path
        line_number = frame.line_number
        if frame.error_type:
            error_type = frame.error_type
            if frame.detail:
                headline = f"{error_type}: {frame.detail}"

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


def _best_failure_frame(block: list[str]) -> _Frame | None:
    frames = _frames_from_block(block)
    implementation_frames = [frame for frame in frames if _is_project_path(frame.path) and not _is_test_path(frame.path)]
    if implementation_frames:
        return implementation_frames[-1]
    project_frames = [frame for frame in frames if _is_project_path(frame.path)]
    if project_frames:
        return project_frames[-1]
    return frames[-1] if frames else None


def _frames_from_block(block: list[str]) -> list[_Frame]:
    frames: list[_Frame] = []
    for line in block:
        stripped = line.strip()
        frame = TRACE_FRAME.match(stripped)
        if frame:
            frames.append(_Frame(path=frame.group("path"), line_number=int(frame.group("line"))))
            continue
        match = FILE_LINE.match(stripped)
        if match:
            frames.append(
                _Frame(
                    path=match.group("path"),
                    line_number=int(match.group("line")),
                    error_type=match.group("etype"),
                    detail=match.group("detail"),
                )
            )
    return frames


def _is_project_path(path: str) -> bool:
    return not PurePath(path).is_absolute()


def _is_test_path(path: str) -> bool:
    parts = PurePath(path).parts
    name = PurePath(path).name
    return name.startswith("test_") or "tests" in parts
