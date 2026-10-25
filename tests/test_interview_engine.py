from datetime import datetime, timezone

import pytest

from testbridge.evidence.store import new_event
from testbridge.mastery.estimator import estimate
from testbridge.mastery.rule import rule_score

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


def interview(score: float, concepts: list[str]) -> object:
    return new_event(
        kind="interview", concept_ids=concepts, outcome="submitted",
        score=score, max_score=1.0,
    )


def test_interview_counts_separately() -> None:
    result = rule_score([interview(0.8, ["c-one"])], "c-one", NOW)
    assert result.interview_observations == 1
    assert result.other_observations == 0
    assert result.exercise_observations == 0
    assert result.score == pytest.approx(0.8)


def test_interview_weight_is_below_exercise() -> None:
    bad_interview = interview(0.0, ["c-one"])
    good_exercise = new_event(
        kind="exercise_attempt", concept_ids=["c-one"], outcome="correct",
        score=1.0, max_score=1.0,
    )
    result = rule_score([bad_interview, good_exercise], "c-one", NOW)
    # exercise 权重 1.0 > interview 0.6
    assert 0.6 < result.score < 0.65


def test_interview_does_not_feed_bkt() -> None:
    events = [interview(1.0, ["c-one"]) for _ in range(5)]
    view = estimate("c-one", events, NOW)
    assert view.bkt_p == pytest.approx(0.3)
    assert view.exercise_observations == 0
    assert view.interview_observations == 5
