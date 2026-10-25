from datetime import datetime, timezone
from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.learning.store import Goal, ReviewState
from testbridge.mastery.estimator import MasteryView
from testbridge.mastery.rule import level_for
from testbridge.recommend.planner import Planner

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"
PACK = load_pack(SAMPLE)
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def view(
    concept_id: str,
    estimate: float,
    observations: int = 0,
    level: str | None = None,
) -> MasteryView:
    return MasteryView(
        concept_id=concept_id, rule_score=estimate, bkt_p=estimate,
        estimate=estimate, confidence=1.0,
        level=level if level is not None else level_for(estimate),
        exercise_observations=observations, other_observations=0,
    )


def review(exercise_id: str, due: str = "2026-10-24T00:00:00+00:00") -> ReviewState:
    return ReviewState(
        learner_id="local", exercise_id=exercise_id, concept_ids=["sensor-time-sync"],
        due=due, stability=1.0, difficulty=5.0,
        reps=1, lapses=0, state="Review", last_review=None,
        card_json={"card_id": 1, "state": 2, "step": 0, "stability": 1.0,
                   "difficulty": 5.0, "due": due, "last_review": None},
    )


def test_due_reviews_come_first() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 1.0, 3),
        "clock-drift": view("clock-drift", 1.0, 3),
        "sensor-time-sync": view("sensor-time-sync", 1.0, 3),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery,
        [review("EX-SYNC-001")], {"sensor-time-sync": 1.0},
    )
    plan = planner.plan(NOW)
    assert plan.items
    assert plan.items[0].type == "review"
    assert plan.items[0].exercise_id == "EX-SYNC-001"


def test_new_concept_requires_prerequisites() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.0),
        "clock-drift": view("clock-drift", 0.0),
        "sensor-time-sync": view("sensor-time-sync", 0.0),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery, [],
        {"timestamp-basics": 0.5, "clock-drift": 0.5, "sensor-time-sync": 1.0},
    )
    plan = planner.plan(NOW)
    assert [item.type for item in plan.items] == ["new"]
    assert "timestamp-basics" in plan.items[0].concept_ids


def test_weak_concepts_are_added() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.2, 2),
        "clock-drift": view("clock-drift", 1.0, 3),
        "sensor-time-sync": view("sensor-time-sync", 0.2, 2),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery, [],
        {"timestamp-basics": 0.5, "clock-drift": 0.5, "sensor-time-sync": 1.0},
    )
    plan = planner.plan(NOW)
    assert any(item.type == "weak" for item in plan.items)


def test_budget_can_leave_only_reviews() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.0),
        "clock-drift": view("clock-drift", 0.0),
        "sensor-time-sync": view("sensor-time-sync", 0.0),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=10), mastery,
        [review("EX-SYNC-001")], {"timestamp-basics": 0.5},
    )
    plan = planner.plan(NOW)
    assert [item.type for item in plan.items] == ["review"]
    assert plan.budget_minutes == 10


def test_empty_plan_has_suggestion() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.9, 5),
        "clock-drift": view("clock-drift", 0.9, 5),
        "sensor-time-sync": view("sensor-time-sync", 0.6, 5),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery, [],
        {"timestamp-basics": 0.5},
    )
    plan = planner.plan(NOW)
    assert plan.empty is True
    assert plan.suggestion
    assert "sensor-time-sync" in plan.suggestion


def test_new_concept_respects_target_level() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.0, level="L2"),
        "clock-drift": view("clock-drift", 0.0),
        "sensor-time-sync": view("sensor-time-sync", 0.0),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery, [],
        {"timestamp-basics": 0.5},
    )
    plan = planner.plan(NOW)
    assert [item for item in plan.items if item.type == "new"] == []


def test_unknown_concept_is_skipped() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.9, 5),
        "clock-drift": view("clock-drift", 0.9, 5),
        "sensor-time-sync": view("sensor-time-sync", 0.9, 5),
        "unknown": view("unknown", 0.2, 2),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery, [], {},
    )
    plan = planner.plan(NOW)
    assert plan.empty is True
    assert all("unknown" not in item.concept_ids for item in plan.items)


def test_future_due_review_is_not_planned() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.9, 5),
        "clock-drift": view("clock-drift", 0.9, 5),
        "sensor-time-sync": view("sensor-time-sync", 0.9, 5),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery,
        [review("EX-SYNC-001", due="2026-10-26T00:00:00+00:00")], {},
    )
    plan = planner.plan(NOW)
    assert plan.items == []


def test_plan_is_deterministic() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.2, 2),
        "clock-drift": view("clock-drift", 1.0, 3),
        "sensor-time-sync": view("sensor-time-sync", 0.2, 2),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery, [],
        {"timestamp-basics": 0.5, "clock-drift": 0.5, "sensor-time-sync": 5.0},
    )
    first = planner.plan(NOW)
    second = planner.plan(NOW)
    assert first.items == second.items
    assert first.total_minutes == second.total_minutes
    assert all(0.0 <= item.priority <= 1.0 for item in first.items)
