from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.contract.models import Concept, Exercise
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


def test_review_reason_uses_exercise_prompt() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 1.0, 3),
        "clock-drift": view("clock-drift", 1.0, 3),
        "sensor-time-sync": view("sensor-time-sync", 1.0, 3),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery,
        [review("EX-SYNC-001")], {},
    )
    plan = planner.plan(NOW)
    assert plan.items[0].reason == "到期复习：两个传感器时间戳相差 20ms，最不可能的根因是？"


def test_priority_orders_on_raw_value_before_clamp() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.2, 2),
        "clock-drift": view("clock-drift", 0.2, 2),
        "sensor-time-sync": view("sensor-time-sync", 1.0, 5),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery, [],
        {"timestamp-basics": 1.5, "clock-drift": 3.0},
    )
    plan = planner.plan(NOW)
    weak = [item for item in plan.items if item.type == "weak"]
    assert [item.concept_ids[0] for item in weak] == ["clock-drift", "timestamp-basics"]
    assert all(item.priority == 1.0 for item in weak)


def pack_with_orphan_concept():
    concept = Concept.model_validate({
        "id": "orphan-concept", "title": "Orphan", "domain": "demo",
        "target_level": "L2",
    })
    exercise = Exercise.model_validate({
        "id": "EX-ORPHAN", "type": "single_choice", "concepts": ["orphan-concept"],
        "level": "L1", "prompt": "Orphan prompt",
        "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        "answer": "a",
    })
    return replace(
        PACK,
        concepts={**PACK.concepts, concept.id: concept},
        exercises={**PACK.exercises, exercise.id: exercise},
    )


def test_weak_concept_without_lesson_falls_back_to_exercise() -> None:
    mastery = {"orphan-concept": view("orphan-concept", 0.2, 2)}
    planner = Planner(
        pack_with_orphan_concept(), Goal(learner_id="local", daily_minutes=45),
        mastery, [], {"orphan-concept": 1.0},
    )
    plan = planner.plan(NOW)
    assert [item.type for item in plan.items] == ["weak"]
    item = plan.items[0]
    assert item.lesson_id is None
    assert item.exercise_id == "EX-ORPHAN"
    assert item.estimated_minutes == 10
    assert item.reason.startswith("掌握度偏低：orphan-concept")


def test_interview_only_concept_is_weak_not_new() -> None:
    mastery = {
        "timestamp-basics": MasteryView(
            concept_id="timestamp-basics", rule_score=0.3, bkt_p=0.3,
            estimate=0.3, confidence=0.0, level="L1",
            exercise_observations=0, other_observations=0,
            interview_observations=2,
        ),
        "clock-drift": view("clock-drift", 1.0, 3),
        "sensor-time-sync": view("sensor-time-sync", 0.2),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery, [],
        {"timestamp-basics": 0.5, "clock-drift": 0.5, "sensor-time-sync": 1.0},
    )
    plan = planner.plan(NOW)
    weak = [item for item in plan.items if item.type == "weak"]
    assert weak
    assert any("面试失分" in item.reason for item in weak)
    assert not any(
        item.type == "new" and "timestamp-basics" in item.concept_ids
        for item in plan.items
    )


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
