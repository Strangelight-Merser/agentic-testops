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
    junit_xml: str = ""

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
class LlmExplanation:
    failure_nodeid: str
    explanation: str
    model: str


@dataclass(frozen=True)
class FlakeResult:
    nodeid: str
    attempts: int
    failed_attempts: int
    verdict: str

    @property
    def pass_rate(self) -> float:
        if self.attempts == 0:
            return 0.0
        return (self.attempts - self.failed_attempts) / self.attempts


@dataclass(frozen=True)
class VerificationResult:
    verdict: str
    applied_suggestions: list[str] = field(default_factory=list)
    guardrail_tests: list[str] = field(default_factory=list)
    guardrail_run: TestRun | None = None
    full_run: TestRun | None = None
    new_failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "applied_suggestions": self.applied_suggestions,
            "guardrail_tests": self.guardrail_tests,
            "guardrail_run": _run_summary(self.guardrail_run),
            "full_run": _run_summary(self.full_run),
            "new_failures": self.new_failures,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class AuditReport:
    project_path: Path
    run: TestRun
    failures: list[Failure]
    diagnoses: list[Diagnosis]
    patch_proposals: list[PatchProposal] = field(default_factory=list)
    fix_suggestions: list[FixSuggestion] = field(default_factory=list)
    rerun: TestRun | None = None
    flake_results: list[FlakeResult] = field(default_factory=list)
    llm_explanations: list[LlmExplanation] = field(default_factory=list)
    verification: VerificationResult | None = None

    @property
    def display_project_path(self) -> str:
        return _portable_project_path(self.project_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": self.display_project_path,
            "command": _portable_command(self.run.command),
            "returncode": self.run.returncode,
            "duration_seconds": self.run.duration_seconds,
            "passed": self.run.passed,
            "timed_out": self.run.timed_out,
            "junit_xml_available": bool(self.run.junit_xml),
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
            "flake_results": [
                {
                    "nodeid": result.nodeid,
                    "attempts": result.attempts,
                    "failed_attempts": result.failed_attempts,
                    "pass_rate": result.pass_rate,
                    "verdict": result.verdict,
                }
                for result in self.flake_results
            ],
            "fix_suggestions": [suggestion.__dict__ for suggestion in self.fix_suggestions],
            "llm_explanations": [explanation.__dict__ for explanation in self.llm_explanations],
            "verification": self.verification.to_dict() if self.verification else None,
            "rerun": {
                "command": _portable_command(self.rerun.command),
                "returncode": self.rerun.returncode,
                "duration_seconds": self.rerun.duration_seconds,
                "passed": self.rerun.passed,
                "timed_out": self.rerun.timed_out,
                "junit_xml_available": bool(self.rerun.junit_xml),
            }
            if self.rerun
            else None,
        }


def _run_summary(run: TestRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "command": _portable_command(run.command),
        "returncode": run.returncode,
        "duration_seconds": run.duration_seconds,
        "passed": run.passed,
        "timed_out": run.timed_out,
    }


def _portable_command(command: list[str]) -> list[str]:
    if len(command) >= 3 and command[1:3] == ["-m", "pytest"]:
        return ["python", *command[1:]]
    return command


def _portable_project_path(project_path: Path) -> str:
    if not project_path.is_absolute():
        text = project_path.as_posix()
        return text or "."
    return project_path.name or "."
