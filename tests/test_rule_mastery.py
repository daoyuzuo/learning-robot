from datetime import datetime, timedelta, timezone

from testbridge.evidence.store import new_event
from testbridge.mastery.rule import confidence_for, level_for, rule_score

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def event(kind: str, outcome: str, concepts: list[str], days_ago: float = 0) -> object:
    item = new_event(kind=kind, concept_ids=concepts, outcome=outcome, score=1.0 if outcome == "correct" else 0.0, max_score=1.0)
    return item.__class__(**{**item.__dict__, "created_at": (NOW - timedelta(days=days_ago)).isoformat()})


def test_no_evidence_is_zero() -> None:
    result = rule_score([], "c-one", NOW)
    assert result.score == 0.0
    assert result.exercise_observations == 0


def test_single_correct_exercise() -> None:
    result = rule_score([event("exercise_attempt", "correct", ["c-one"])], "c-one", NOW)
    assert result.score == 1.0
    assert result.exercise_observations == 1


def test_recent_evidence_outweighs_old() -> None:
    old = event("exercise_attempt", "correct", ["c-one"], days_ago=60)
    recent = event("exercise_attempt", "incorrect", ["c-one"], days_ago=0)
    result = rule_score([old, recent], "c-one", NOW)
    assert 0.0 < result.score < 0.5


def test_self_assess_has_lower_weight() -> None:
    exercise = event("exercise_attempt", "incorrect", ["c-one"])
    self_assess = event("self_assess", "submitted", ["c-one"])
    result = rule_score([exercise, self_assess], "c-one", NOW)
    assert result.other_observations == 1
    assert result.score < 0.5


def test_multi_concept_event_is_shared() -> None:
    shared = event("exercise_attempt", "correct", ["c-one", "c-two"])
    solo = event("exercise_attempt", "incorrect", ["c-one"])
    result = rule_score([shared, solo], "c-one", NOW)
    assert result.score < 1.0


def test_interview_has_own_bucket() -> None:
    result = rule_score(
        [event("interview", "submitted", ["c-one"])], "c-one", NOW
    )
    assert result.interview_observations == 1
    assert result.other_observations == 0


def test_levels_and_confidence() -> None:
    assert level_for(0.1) == "L0"
    assert level_for(0.3) == "L1"
    assert level_for(0.6) == "L2"
    assert level_for(0.8) == "L3"
    assert level_for(0.95) == "L4"
    assert confidence_for(0, 0) == 0.0
    assert confidence_for(5, 0) == 1.0
