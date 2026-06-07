from __future__ import annotations

import json
from pathlib import Path

from .models import AuditReport


def write_markdown_report(report: AuditReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(report), encoding="utf-8")


def write_json_report(report: AuditReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def render_markdown(report: AuditReport) -> str:
    status = _status(report.run)
    lines = [
        "# Agentic TestOps Audit Report",
        "",
        f"- Project: `{report.project_path}`",
        f"- Status: **{status}**",
        f"- Command: `{_render_command(report.run.command)}`",
        f"- Duration: `{report.run.duration_seconds:.2f}s`",
        f"- Return code: `{report.run.returncode}`",
        f"- Parsed failures: `{len(report.failures)}`",
        "",
    ]

    if report.run.passed:
        lines.extend(["## Result", "", "All tests passed. No repair advice was generated.", ""])
        return "\n".join(lines)

    if report.rerun:
        status = _status(report.rerun)
        lines.extend(
            [
                "## Agentic Rerun",
                "",
                f"- Status: **{status}**",
                f"- Command: `{_render_command(report.rerun.command)}`",
                f"- Duration: `{report.rerun.duration_seconds:.2f}s`",
                "",
            ]
        )

    lines.extend(["## Diagnosis", ""])
    for index, diagnosis in enumerate(report.diagnoses, start=1):
        failure = diagnosis.failure
        location = ""
        if failure.file_path:
            location = f" at `{failure.file_path}`"
            if failure.line_number:
                location += f":{failure.line_number}"
        lines.extend(
            [
                f"### {index}. `{failure.nodeid}`",
                "",
                f"- Headline: {failure.headline}{location}",
                f"- Category: `{diagnosis.category}`",
                f"- Confidence: `{diagnosis.confidence}`",
                f"- Summary: {diagnosis.summary}",
                "",
                "Evidence:",
            ]
        )
        for item in diagnosis.evidence:
            lines.append(f"- `{item}`")
        lines.extend(["", "Repair advice:"])
        for item in diagnosis.repair_advice:
            lines.append(f"- {item}")
        lines.append("")

    if report.patch_proposals:
        lines.extend(["## Patch Proposals", ""])
        for index, proposal in enumerate(report.patch_proposals, start=1):
            location = proposal.target_file or "unknown"
            if proposal.target_line:
                location = f"{location}:{proposal.target_line}"
            lines.extend(
                [
                    f"### {index}. `{proposal.failure_nodeid}`",
                    "",
                    f"- Target: `{location}`",
                    f"- Confidence: `{proposal.confidence}`",
                    f"- Action: {proposal.action}",
                    f"- Rationale: {proposal.rationale}",
                    "- Guardrail tests:",
                ]
            )
            for nodeid in proposal.guardrail_tests:
                lines.append(f"  - `{nodeid}`")
            lines.append("")

    lines.extend(
        [
            "## Raw Pytest Output",
            "",
            "```text",
            _trim(report.run.stdout + "\n" + report.run.stderr),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _trim(text: str, limit: int = 12000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... output truncated ..."


def _status(run) -> str:
    if run.timed_out:
        return "TIMEOUT"
    return "PASS" if run.passed else "FAIL"


def _render_command(command: list[str]) -> str:
    if len(command) >= 3 and command[1:3] == ["-m", "pytest"]:
        return " ".join(["python", *command[1:]])
    return " ".join(command)
