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
class AuditReport:
    project_path: Path
    run: TestRun
    failures: list[Failure]
    diagnoses: list[Diagnosis]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": str(self.project_path),
            "command": self.run.command,
            "returncode": self.run.returncode,
            "duration_seconds": self.run.duration_seconds,
            "passed": self.run.passed,
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
        }
