"""Quality report model and scoring helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class QualityIssue:
    code: str
    message: str
    severity: Severity
    lesson_id: str | None = None
    concept_id: str | None = None
    resource_id: str | None = None

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "lesson_id": self.lesson_id,
            "concept_id": self.concept_id,
            "resource_id": self.resource_id,
        }


@dataclass(frozen=True)
class QualityMetric:
    key: str
    label: str
    earned: int
    possible: int
    detail: str

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "earned": self.earned,
            "possible": self.possible,
            "detail": self.detail,
        }


def round_half_up(value: float) -> int:
    return int(value + 0.5)


def proportional(count: int, total: int, possible: int) -> int:
    if total <= 0 or possible <= 0:
        return 0
    return round_half_up(possible * (count / total))


def _issue_key(issue: QualityIssue) -> tuple:
    return (
        issue.code,
        issue.lesson_id or "",
        issue.concept_id or "",
        issue.resource_id or "",
        issue.message,
    )


@dataclass(frozen=True)
class QualityReport:
    score: int = 0
    metrics: list[QualityMetric] = field(default_factory=list)
    errors: list[QualityIssue] = field(default_factory=list)
    warnings: list[QualityIssue] = field(default_factory=list)
    provenance_evaluated: bool = False
    research_evaluated: bool = False
    earned: int = 0
    possible: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "earned": self.earned,
            "possible": self.possible,
            "ok": self.ok,
            "provenance_evaluated": self.provenance_evaluated,
            "research_evaluated": self.research_evaluated,
            "metrics": [metric.as_dict() for metric in self.metrics],
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }


def build_report(
    metrics: list[QualityMetric],
    errors: list[QualityIssue],
    warnings: list[QualityIssue],
    *,
    provenance_evaluated: bool,
    research_evaluated: bool,
) -> QualityReport:
    earned = sum(metric.earned for metric in metrics)
    possible = sum(metric.possible for metric in metrics)
    score = round_half_up(100 * earned / possible) if possible else 0
    return QualityReport(
        score=score,
        metrics=list(metrics),
        errors=sorted(errors, key=_issue_key),
        warnings=sorted(warnings, key=_issue_key),
        provenance_evaluated=provenance_evaluated,
        research_evaluated=research_evaluated,
        earned=earned,
        possible=possible,
    )
