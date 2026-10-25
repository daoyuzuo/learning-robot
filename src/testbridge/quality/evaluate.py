"""Combine structural and provenance checks into one quality report."""

from __future__ import annotations

from pathlib import Path

from testbridge.content.repository import ContentValidationError, load_pack
from testbridge.contract.validator import ValidationReport
from testbridge.quality.provenance import evaluate_provenance
from testbridge.quality.report import QualityReport, build_report
from testbridge.quality.structural import evaluate_structural


class QualityUnavailable(Exception):
    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        super().__init__(f"content pack has {len(report.errors)} error(s)")


def evaluate_pack(
    pack_dir: Path,
    *,
    research_dir: Path | None = None,
    budget: int | None = None,
) -> QualityReport:
    try:
        pack = load_pack(pack_dir)
    except ContentValidationError as exc:
        raise QualityUnavailable(exc.report) from exc

    structural = evaluate_structural(pack)
    provenance = evaluate_provenance(
        pack,
        research_dir,
        budget,
        include_metrics=research_dir is not None,
    )
    return build_report(
        structural.metrics + provenance.metrics,
        structural.errors + provenance.errors,
        structural.warnings + provenance.warnings,
        provenance_evaluated=research_dir is not None,
        research_evaluated=research_dir is not None,
    )


def evaluate_draft(
    pack_dir: Path,
    *,
    research_dir: Path,
    budget: int,
) -> QualityReport:
    return evaluate_pack(pack_dir, research_dir=research_dir, budget=budget)
