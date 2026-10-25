"""JD-weighted readiness and gap report."""

from __future__ import annotations

from dataclasses import dataclass, field

from testbridge.content.repository import ContentPack
from testbridge.learning.store import Goal
from testbridge.mastery.estimator import MasteryView
from testbridge.readiness import LEVEL_ORDER, ReadinessView, calculate_readiness


@dataclass(frozen=True)
class GapRow:
    concept_id: str
    title: str
    weight: float
    estimate: float
    level: str
    target_level: str
    level_gap: int


@dataclass(frozen=True)
class MatchReport:
    readiness: ReadinessView
    weights: dict[str, float]
    gaps: list[GapRow] = field(default_factory=list)
    top: list[GapRow] = field(default_factory=list)
    uncovered: list[str] = field(default_factory=list)


def build_report(
    pack: ContentPack,
    goal: Goal,
    mastery: dict[str, MasteryView],
    uncovered: list[str] | None = None,
) -> MatchReport:
    readiness = calculate_readiness(pack, goal, mastery)
    weights = {
        concept_id: goal.concept_overrides.get(concept_id, 1.0)
        for concept_id in pack.concepts
        if goal.concept_overrides.get(concept_id, 1.0) > 1.0
    }

    gaps: list[GapRow] = []
    for concept_id, weight in weights.items():
        concept = pack.concepts[concept_id]
        view = mastery.get(concept_id)
        if view is None:
            continue
        level_gap = max(
            0,
            LEVEL_ORDER[concept.target_level] - LEVEL_ORDER.get(view.level, 0),
        )
        if level_gap == 0:
            continue
        gaps.append(GapRow(
            concept_id=concept_id,
            title=concept.title,
            weight=weight,
            estimate=view.estimate,
            level=view.level,
            target_level=concept.target_level,
            level_gap=level_gap,
        ))

    gaps.sort(key=lambda row: (
        -(row.weight * row.level_gap),
        -(row.weight * (1 - row.estimate)),
        row.concept_id,
    ))
    return MatchReport(
        readiness=readiness,
        weights=weights,
        gaps=gaps,
        top=gaps[:3],
        uncovered=list(uncovered or []),
    )
