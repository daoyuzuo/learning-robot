from testbridge.contract.models import Exercise, Hint, RubricItem, ShortAnswer
from testbridge.exercise.grading import get_hint, grade


def choice() -> Exercise:
    return Exercise(
        id="EX-C", type="single_choice", concepts=["c-one"], level="L1",
        prompt="Pick", options=[{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        answer="a", hints=[Hint(level=1, text="think")],
    )


def test_single_choice() -> None:
    assert grade(choice(), "a").correct is True
    assert grade(choice(), "b").correct is False


def test_multi_choice_partial() -> None:
    ex = Exercise(
        id="EX-M", type="multi_choice", concepts=["c-one"], level="L2",
        prompt="Pick", options=[{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        answer=["a", "b"],
    )
    result = grade(ex, ["a"])
    assert result.outcome == "partial"
    assert result.score == 0.5


def test_short_answer_keywords() -> None:
    ex = Exercise(
        id="EX-S", type="short_answer", concepts=["c-one"], level="L2",
        prompt="Explain", answer=ShortAnswer(accepted=["时间戳", "阈值"], min_hits=1),
        rubric=[RubricItem(dimension="x", weight=1.0, criteria="x")],
    )
    assert grade(ex, "时间戳要对齐").correct is True
    assert grade(ex, "不知道").correct is False


def test_self_assess_scores_checked_dimensions() -> None:
    ex = Exercise(
        id="EX-A", type="self_assess", concepts=["c-one"], level="L2",
        prompt="Rate", rubric=[
            RubricItem(dimension="机制", weight=0.5, criteria="x"),
            RubricItem(dimension="测试", weight=0.5, criteria="y"),
        ],
    )
    result = grade(ex, {"checked": ["机制"]})
    assert result.outcome == "submitted"
    assert result.score == 0.5


def test_artifact_requires_path() -> None:
    ex = Exercise(
        id="EX-F", type="artifact", concepts=["c-one"], level="L3",
        prompt="Upload", artifact={"accept": ["log"], "max_size_mb": 1},
        rubric=[RubricItem(dimension="x", weight=1.0, criteria="x")],
    )
    assert grade(ex, {"path": "a.log"}).outcome == "submitted"
    assert grade(ex, {"notes": "no path"}).outcome == "incorrect"


def test_hint_levels() -> None:
    ex = choice()
    assert get_hint(ex, 1) == "think"
    assert get_hint(ex, 2) is None
