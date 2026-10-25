"""Combine rule-based mastery and BKT with a cold-start handoff."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from testbridge.evidence.store import EvidenceEvent
from testbridge.mastery.bkt import BKTParams, BKTState, initial_state, observe
from testbridge.mastery.rule import confidence_for, level_for, rule_score

HANDOFF_OBSERVATIONS = 3


@dataclass(frozen=True)
class MasteryView:
    concept_id: str
    rule_score: float
    bkt_p: float
    estimate: float
    confidence: float
    level: str
    exercise_observations: int
    other_observations: int
    interview_observations: int = 0


def replay_bkt(
    events: Iterable[EvidenceEvent],
    concept_id: str,
    params: BKTParams | None = None,
) -> BKTState:
    state = initial_state(params)
    ordered = sorted(events, key=lambda event: (event.created_at, event.id))
    for event in ordered:
        if event.kind != "exercise_attempt" or concept_id not in event.concept_ids:
            continue
        state = observe(state, event.outcome == "correct", params)
    return state


def estimate(
    concept_id: str,
    events: Iterable[EvidenceEvent],
    now: datetime,
    bkt_state: BKTState | None = None,
    params: BKTParams | None = None,
) -> MasteryView:
    events = list(events)
    rule = rule_score(events, concept_id, now)
    state = bkt_state or replay_bkt(events, concept_id, params)
    estimate_value = state.p if state.observations >= HANDOFF_OBSERVATIONS else rule.score
    return MasteryView(
        concept_id=concept_id,
        rule_score=rule.score,
        bkt_p=state.p,
        estimate=estimate_value,
        confidence=confidence_for(rule.exercise_observations, rule.other_observations),
        level=level_for(estimate_value),
        exercise_observations=rule.exercise_observations,
        other_observations=rule.other_observations,
        interview_observations=rule.interview_observations,
    )
