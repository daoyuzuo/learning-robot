import pytest

from testbridge.contract.models import Exercise, Hint, RubricItem, ShortAnswer
from testbridge.exercise.grading import get_hint, grade, kind_for_exercise, normalize


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


def test_kind_for_exercise_maps_all_types() -> None:
    assert kind_for_exercise("single_choice") == "exercise_attempt"
    assert kind_for_exercise("multi_choice") == "exercise_attempt"
    assert kind_for_exercise("short_answer") == "exercise_attempt"
    assert kind_for_exercise("self_assess") == "self_assess"
    assert kind_for_exercise("artifact") == "artifact"


def test_kind_for_exercise_defaults_to_exercise_attempt() -> None:
    assert kind_for_exercise("unknown") == "exercise_attempt"


def test_hint_levels() -> None:
    ex = choice()
    assert get_hint(ex, 1) == "think"
    assert get_hint(ex, 2) is None


def multi() -> Exercise:
    return Exercise(
        id="EX-M2", type="multi_choice", concepts=["c-one"], level="L2",
        prompt="Pick", options=[
            {"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"},
        ],
        answer=["a", "b"],
    )


def test_multi_choice_false_positive_is_penalized() -> None:
    result = grade(multi(), ["a", "b", "c"])
    assert result.outcome == "partial"
    assert result.correct is False
    assert result.score < 1.0
    assert result.details["false_positives"] == ["c"]


def test_multi_choice_exact_match_scores_full() -> None:
    result = grade(multi(), ["a", "b"])
    assert result.correct is True
    assert result.score == 1.0


def test_multi_choice_no_hits_scores_zero() -> None:
    result = grade(multi(), ["c"])
    assert result.outcome == "incorrect"
    assert result.score == 0.0


def test_artifact_rejects_non_path_values() -> None:
    for bad in (None, 123, "  "):
        result = grade(artifact(), {"path": bad})
        assert result.outcome == "incorrect", bad
        assert result.correct is False
        assert result.score == 0.0


def test_artifact_accepts_stripped_string_path() -> None:
    result = grade(artifact(), {"path": "  a.log  "})
    assert result.outcome == "submitted"


def artifact() -> Exercise:
    return Exercise(
        id="EX-F2", type="artifact", concepts=["c-one"], level="L3",
        prompt="Upload", artifact={"accept": ["log"], "max_size_mb": 1},
        rubric=[RubricItem(dimension="x", weight=1.0, criteria="x")],
    )


def test_normalize_strips_cjk_punctuation_whitespace_and_case() -> None:
    assert normalize("  Hello，世界。 ") == "hello世界"
    assert normalize("A\t B\nC！？") == "abc"


def test_unsupported_type_raises() -> None:
    ex = choice().model_copy(update={"type": "unknown"})
    with pytest.raises(ValueError):
        grade(ex, "a")
