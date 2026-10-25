"""Rule-based, explainable mastery from evidence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from testbridge.evidence.store import EvidenceEvent
from testbridge.learning.timeutil import parse_iso

KIND_WEIGHTS = {"exercise_attempt": 1.0, "self_assess": 0.5, "artifact": 0.7}
HALF_LIFE_DAYS = 30.0
LEVEL_THRESHOLDS = ((0.90, "L4"), (0.75, "L3"), (0.50, "L2"), (0.25, "L1"))


@dataclass(frozen=True)
class RuleResult:
    score: float
    exercise_observations: int
    other_observations: int
    weight_sum: float


def event_score(event: EvidenceEvent) -> float:
    if event.score is not None and event.max_score:
        return max(0.0, min(1.0, event.score / event.max_score))
    return {"correct": 1.0, "partial": 0.5, "incorrect": 0.0, "submitted": 0.5}.get(
        event.outcome or "", 0.5
    )


def rule_score(events: Iterable[EvidenceEvent], concept_id: str, now: datetime) -> RuleResult:
    numerator = 0.0
    denominator = 0.0
    exercise_observations = 0
    other_observations = 0
    for event in events:
        if concept_id not in event.concept_ids:
            continue
        kind_weight = KIND_WEIGHTS.get(event.kind)
        if kind_weight is None:
            continue
        if event.kind == "exercise_attempt":
            exercise_observations += 1
        else:
            other_observations += 1
        age_days = max(0.0, (now - parse_iso(event.created_at)).total_seconds() / 86400)
        decay = 0.5 ** (age_days / HALF_LIFE_DAYS)
        share = 1.0 / max(1, len(event.concept_ids))
        weight = kind_weight * decay * share
        numerator += weight * event_score(event)
        denominator += weight
    score = numerator / denominator if denominator else 0.0
    return RuleResult(score, exercise_observations, other_observations, denominator)


def level_for(estimate: float) -> str:
    for threshold, level in LEVEL_THRESHOLDS:
        if estimate >= threshold:
            return level
    return "L0"


def confidence_for(exercise_observations: int, other_observations: int) -> float:
    return min(1.0, (exercise_observations + 0.5 * other_observations) / 5.0)
