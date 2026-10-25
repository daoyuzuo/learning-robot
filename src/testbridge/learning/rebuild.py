"""Replay evidence into rebuildable mastery and review state."""

from __future__ import annotations

from dataclasses import dataclass

from testbridge.learning.service import LearningService
from testbridge.learning.store import MasteryState
from testbridge.learning.timeutil import iso
from testbridge.mastery.bkt import initial_state, observe
from testbridge.mastery.estimator import HANDOFF_OBSERVATIONS
from testbridge.mastery.rule import confidence_for, level_for, rule_score
from testbridge.schedule.fsrs import review_event


@dataclass(frozen=True)
class RebuildResult:
    events: int
    concepts: int
    reviews: int


def rebuild_state(service: LearningService) -> RebuildResult:
    all_events = service.evidence.list(limit=1_000_000)
    superseded = {event.supersedes for event in all_events if event.supersedes}
    events = sorted(
        (
            event
            for event in all_events
            if event.id not in superseded and event.learner_id == service.learner_id
        ),
        key=lambda event: (event.created_at, event.id),
    )

    touched = [
        concept_id
        for concept_id in service.pack.concepts
        if any(concept_id in event.concept_ids for event in events)
    ]
    bkt = {concept_id: initial_state() for concept_id in touched}
    reviews = {}

    for event in events:
        for concept_id in event.concept_ids:
            if concept_id not in bkt:
                continue
            if event.kind == "exercise_attempt":
                bkt[concept_id] = observe(bkt[concept_id], event.outcome == "correct")
        if event.kind == "exercise_attempt" and event.exercise_id in service.pack.exercises:
            reviews[event.exercise_id] = review_event(
                event.exercise_id,
                event.concept_ids,
                event,
                previous=reviews.get(event.exercise_id),
                learner_id=service.learner_id,
            )

    now = service.now()
    mastery = {}
    for concept_id in touched:
        rule = rule_score(events, concept_id, now)
        value = (
            bkt[concept_id].p
            if bkt[concept_id].observations >= HANDOFF_OBSERVATIONS
            else rule.score
        )
        mastery[concept_id] = MasteryState(
            learner_id=service.learner_id,
            concept_id=concept_id,
            rule_score=rule.score,
            bkt_p=bkt[concept_id].p,
            exercise_observations=bkt[concept_id].observations,
            other_observations=rule.other_observations,
            estimate=value,
            confidence=confidence_for(
                bkt[concept_id].observations, rule.other_observations
            ),
            level=level_for(value),
            updated_at=iso(now),
        )

    service.store.replace_all(service.learner_id, mastery, reviews)
    return RebuildResult(events=len(events), concepts=len(mastery), reviews=len(reviews))
