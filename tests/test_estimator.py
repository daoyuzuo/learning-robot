from datetime import datetime, timezone

from testbridge.evidence.store import new_event
from testbridge.mastery.estimator import HANDOFF_OBSERVATIONS, estimate
from testbridge.mastery.bkt import initial_state

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def exercise(outcome: str) -> object:
    return new_event(
        kind="exercise_attempt", concept_ids=["c-one"], outcome=outcome,
        score=1.0 if outcome == "correct" else 0.0, max_score=1.0,
    )


def test_uses_rule_before_handoff() -> None:
    events = [exercise("correct"), exercise("incorrect")]
    view = estimate("c-one", events, NOW)
    assert view.exercise_observations == 2
    assert view.estimate == view.rule_score


def test_uses_bkt_after_handoff() -> None:
    events = [exercise("correct") for _ in range(HANDOFF_OBSERVATIONS)]
    view = estimate("c-one", events, NOW)
    assert view.exercise_observations == 3
    assert view.estimate == view.bkt_p
    assert view.estimate != view.rule_score


def test_confidence_and_level() -> None:
    events = [exercise("correct") for _ in range(5)]
    view = estimate("c-one", events, NOW)
    assert view.confidence == 1.0
    assert view.level in {"L1", "L2", "L3", "L4"}


def test_non_exercise_kinds_stay_on_rule_score() -> None:
    events = [
        new_event(
            kind="self_assess", concept_ids=["c-one"], outcome="submitted",
            score=0.5, max_score=1.0,
        ),
        new_event(
            kind="artifact", concept_ids=["c-one"], outcome="submitted",
            score=0.7, max_score=1.0,
        ),
    ]
    view = estimate("c-one", events, NOW)
    assert view.exercise_observations == 0
    assert view.other_observations == 2
    assert view.estimate == view.rule_score
    assert view.bkt_p == initial_state().p


def test_explicit_bkt_state_is_used() -> None:
    state = initial_state()
    view = estimate("c-one", [], NOW, bkt_state=state)
    assert view.bkt_p == state.p
    assert view.estimate == 0.0  # rule score, because observations < 3
