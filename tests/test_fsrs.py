from datetime import datetime, timezone

from fsrs import Rating

from testbridge.evidence.store import new_event
from testbridge.schedule.fsrs import rating_for, review_event

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def attempt(outcome: str, hints: int = 0, duration: int = 0) -> object:
    return new_event(
        kind="exercise_attempt", concept_ids=["c-one"], outcome=outcome,
        score=1.0 if outcome == "correct" else 0.0, max_score=1.0,
        payload={"hints_used": hints, "duration_ms": duration},
    )


def test_rating_mapping() -> None:
    assert rating_for(attempt("incorrect")) == Rating.Again
    assert rating_for(attempt("partial")) == Rating.Hard
    assert rating_for(attempt("correct", hints=1)) == Rating.Hard
    assert rating_for(attempt("correct", duration=10_000)) == Rating.Easy
    assert rating_for(attempt("correct", duration=60_000)) == Rating.Good


def test_review_creates_card() -> None:
    state = review_event("EX-ONE", ["c-one"], attempt("correct"))
    assert state.exercise_id == "EX-ONE"
    assert state.reps == 1
    assert state.state == "Review"
    assert state.due
    assert state.card_json["due"] == state.due


def test_review_updates_existing_card() -> None:
    first = review_event("EX-ONE", ["c-one"], attempt("correct"))
    second = review_event("EX-ONE", ["c-one"], attempt("incorrect"), previous=first)
    assert second.reps == 2
    assert second.lapses == 1
    assert second.state in {"Review", "Relearning"}
