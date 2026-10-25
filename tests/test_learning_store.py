from datetime import datetime, timezone
from pathlib import Path

from testbridge.learning.store import Goal, LearningStore, MasteryState, ReviewState


def state(concept_id: str = "c-one") -> MasteryState:
    return MasteryState(
        learner_id="local", concept_id=concept_id, rule_score=0.5, bkt_p=0.4,
        exercise_observations=2, other_observations=1, estimate=0.5,
        confidence=0.5, level="L2", updated_at="2026-10-25T00:00:00+00:00",
    )


def review(exercise_id: str = "EX-ONE", due: str = "2026-10-25T00:00:00+00:00") -> ReviewState:
    return ReviewState(
        learner_id="local", exercise_id=exercise_id, concept_ids=["c-one"],
        due=due, stability=1.0, difficulty=5.0, reps=1, lapses=0,
        state="Review", last_review="2026-10-24T00:00:00+00:00",
        card_json={"card_id": 1, "state": 2, "step": 0, "stability": 1.0,
                   "difficulty": 5.0, "due": due, "last_review": "2026-10-24T00:00:00+00:00"},
    )


def test_goal_defaults_and_round_trip(tmp_path: Path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    assert store.get_goal("local").daily_minutes == 45
    store.set_goal(Goal(learner_id="local", target_role="测试开发", daily_minutes=60,
                        concept_overrides={"c-one": 1.5}))
    goal = store.get_goal("local")
    assert goal.daily_minutes == 60
    assert goal.concept_overrides == {"c-one": 1.5}


def test_mastery_upsert_and_list(tmp_path: Path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    store.upsert_mastery(state())
    assert store.get_mastery("local", "c-one").estimate == 0.5
    assert set(store.list_mastery("local")) == {"c-one"}


def test_review_upsert_and_due_filter(tmp_path: Path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    store.upsert_review(review("EX-ONE", "2026-10-24T00:00:00+00:00"))
    store.upsert_review(review("EX-TWO", "2026-10-26T00:00:00+00:00"))
    due = store.due_reviews("local", datetime(2026, 10, 25, tzinfo=timezone.utc))
    assert [item.exercise_id for item in due] == ["EX-ONE"]
    assert store.get_review("local", "EX-ONE").concept_ids == ["c-one"]


def test_replace_all_and_clear(tmp_path: Path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    store.upsert_mastery(state("c-old"))
    store.replace_all("local", {"c-one": state()}, {"EX-ONE": review()})
    assert set(store.list_mastery("local")) == {"c-one"}
    assert set(store.list_reviews("local")) == {"EX-ONE"}
    store.clear_mastery("local")
    store.clear_reviews("local")
    assert store.list_mastery("local") == {}
    assert store.list_reviews("local") == {}
