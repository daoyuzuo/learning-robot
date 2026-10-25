"""Exercise-level FSRS scheduling with automatic ratings."""

from __future__ import annotations

from fsrs import Card, Rating, Scheduler

from testbridge.evidence.store import EvidenceEvent
from testbridge.learning.store import ReviewState
from testbridge.learning.timeutil import iso, parse_iso

SCHEDULER = Scheduler(
    learning_steps=(),
    relearning_steps=(),
    enable_fuzzing=False,
)


def rating_for(event: EvidenceEvent) -> Rating:
    if event.outcome == "incorrect":
        return Rating.Again
    if event.outcome == "partial":
        return Rating.Hard
    payload = event.payload or {}
    hints = int(payload.get("hints_used", 0) or 0)
    duration = int(payload.get("duration_ms", 0) or 0)
    if event.outcome == "correct":
        if hints > 0:
            return Rating.Hard
        if 0 < duration <= 20_000:
            return Rating.Easy
        return Rating.Good
    return Rating.Good


def review_event(
    exercise_id: str,
    concept_ids: list[str],
    event: EvidenceEvent,
    previous: ReviewState | None = None,
    learner_id: str = "local",
) -> ReviewState:
    card = Card.from_dict(previous.card_json) if previous else Card()
    rating = rating_for(event)
    reps = (previous.reps if previous else 0) + 1
    lapses = previous.lapses if previous else 0
    if previous and rating == Rating.Again and previous.state in {"Review", "Relearning"}:
        lapses += 1
    card, _ = SCHEDULER.review_card(
        card, rating, review_datetime=parse_iso(event.created_at)
    )
    return ReviewState(
        learner_id=learner_id,
        exercise_id=exercise_id,
        concept_ids=list(concept_ids),
        due=iso(card.due),
        stability=card.stability or 0.0,
        difficulty=card.difficulty or 0.0,
        reps=reps,
        lapses=lapses,
        state=card.state.name,
        last_review=iso(card.last_review) if card.last_review else None,
        card_json=card.to_dict(),
    )
