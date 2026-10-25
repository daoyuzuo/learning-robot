from pathlib import Path

from testbridge.tutor.review import RubricVerdict, TutorReview
from testbridge.tutor.review_store import ExerciseReviewStore

REVIEW = TutorReview(
    verdict="partial",
    explanation="漏了重传代价。",
    strengths=["方向对"],
    gaps=["没提重传"],
    rubric=[RubricVerdict("机制", True, "对")],
    suggested_score=0.5,
)


def test_put_and_get_round_trip(tmp_path: Path) -> None:
    store = ExerciseReviewStore(tmp_path / "r.db")
    store.put(
        evidence_id="e1", learner_id="local", lesson_id="L-1",
        exercise_id="EX-1", review=REVIEW, model="demo", prompt_version="review/1",
    )

    stored = store.get("e1")

    assert stored is not None
    assert stored.verdict == "partial"
    assert stored.strengths == ["方向对"]
    assert stored.rubric == [RubricVerdict("机制", True, "对")]
    assert stored.suggested_score == 0.5
    assert stored.model == "demo"


def test_put_overwrites_same_evidence(tmp_path: Path) -> None:
    store = ExerciseReviewStore(tmp_path / "r.db")
    kwargs = dict(
        evidence_id="e1", learner_id="local", lesson_id="L-1",
        exercise_id="EX-1", model="demo", prompt_version="review/1",
    )
    store.put(review=REVIEW, **kwargs)
    store.put(review=TutorReview(verdict="correct", explanation="改好了"), **kwargs)

    assert store.get("e1").verdict == "correct"


def test_get_missing_returns_none(tmp_path: Path) -> None:
    assert ExerciseReviewStore(tmp_path / "r.db").get("nope") is None
