from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar


@dataclass(frozen=True)
class TestRun:
    __test__: ClassVar[bool] = False

    command: list[str]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class Failure:
    nodeid: str
    headline: str
    file_path: str | None = None
    line_number: int | None = None
    error_type: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class Diagnosis:
    failure: Failure
    category: str
    confidence: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    repair_advice: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PatchProposal:
    failure_nodeid: str
    target_file: str | None
    target_line: int | None
    action: str
    rationale: str
    confidence: str
    guardrail_tests: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FixSuggestion:
    failure_nodeid: str
    target_file: str
    title: str
    explanation: str
    confidence: str
    diff: str
    guardrail_tests: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuditReport:
    project_path: Path
    run: TestRun
    failures: list[Failure]
    diagnoses: list[Diagnosis]
    patch_proposals: list[PatchProposal] = field(default_factory=list)
    fix_suggestions: list[FixSuggestion] = field(default_factory=list)
    rerun: TestRun | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": str(self.project_path),
            "command": _portable_command(self.run.command),
            "returncode": self.run.returncode,
            "duration_seconds": self.run.duration_seconds,
            "passed": self.run.passed,
            "timed_out": self.run.timed_out,
            "failures": [failure.__dict__ for failure in self.failures],
            "diagnoses": [
                {
                    "failure": diagnosis.failure.__dict__,
                    "category": diagnosis.category,
                    "confidence": diagnosis.confidence,
                    "summary": diagnosis.summary,
                    "evidence": diagnosis.evidence,
                    "repair_advice": diagnosis.repair_advice,
                }
                for diagnosis in self.diagnoses
            ],
            "patch_proposals": [proposal.__dict__ for proposal in self.patch_proposals],
            "fix_suggestions": [suggestion.__dict__ for suggestion in self.fix_suggestions],
            "rerun": {
                "command": _portable_command(self.rerun.command),
                "returncode": self.rerun.returncode,
                "duration_seconds": self.rerun.duration_seconds,
                "passed": self.rerun.passed,
                "timed_out": self.rerun.timed_out,
            }
            if self.rerun
            else None,
        }


def _portable_command(command: list[str]) -> list[str]:
    if len(command) >= 3 and command[1:3] == ["-m", "pytest"]:
        return ["python", *command[1:]]
    return command
