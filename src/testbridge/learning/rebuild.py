"""Replay evidence into rebuildable mastery and review state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from testbridge.evidence.store import event_problem
from testbridge.learning.mastery_builder import build_mastery_state
from testbridge.learning.service import LearningService
from testbridge.schedule.fsrs import review_event


@dataclass(frozen=True)
class RebuildResult:
    events: int
    concepts: int
    reviews: int
    skipped_concepts: list[str] = field(default_factory=list)
    skipped_exercises: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def rebuild_state(service: LearningService) -> RebuildResult:
    warnings: list[str] = []
    events = []
    for event in sorted(
        service.visible_events(),
        key=lambda item: (item.created_at, item.id),
    ):
        problem = event_problem(asdict(event))
        if problem:
            warnings.append(f"skipped evidence {event.id}: {problem}")
            continue
        events.append(event)

    seen = {concept_id for event in events for concept_id in event.concept_ids}
    touched = [
        concept_id
        for concept_id in service.pack.concepts
        if concept_id in seen
    ]

    skipped_concepts = set()
    skipped_exercises = set()
    reviews = {}

    for event in events:
        for concept_id in dict.fromkeys(event.concept_ids):
            if concept_id not in service.pack.concepts:
                skipped_concepts.add(concept_id)
        if event.kind != "exercise_attempt" or not event.exercise_id:
            continue
        if event.exercise_id not in service.pack.exercises:
            skipped_exercises.add(event.exercise_id)
            continue
        reviews[event.exercise_id] = review_event(
            event.exercise_id,
            event.concept_ids,
            event,
            previous=reviews.get(event.exercise_id),
            learner_id=service.learner_id,
        )

    now = service.now()
    mastery = {
        concept_id: build_mastery_state(
            learner_id=service.learner_id,
            concept_id=concept_id,
            events=events,
            now=now,
        )
        for concept_id in touched
    }

    service.store.replace_all(service.learner_id, mastery, reviews)
    return RebuildResult(
        events=len(events),
        concepts=len(mastery),
        reviews=len(reviews),
        skipped_concepts=sorted(skipped_concepts),
        skipped_exercises=sorted(skipped_exercises),
        warnings=warnings,
    )
