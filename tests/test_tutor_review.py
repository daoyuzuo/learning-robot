from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.evidence.store import new_event
from testbridge.tutor.review import build_review_context, parse_review

PACK = load_pack(Path(__file__).parents[1] / "content-packs" / "ros2-qos")


def submission(exercise_id: str = "EX-QOS-002", response="a") -> object:
    return new_event(
        kind="exercise_attempt",
        lesson_id="L-QOS-002",
        exercise_id=exercise_id,
        concept_ids=["dds-qos-policies"],
        outcome="incorrect",
        score=0.0,
        max_score=1.0,
        payload={"response": response},
    )


def test_context_includes_answer_explanation_and_response() -> None:
    context = build_review_context(PACK, submission())
    assert "100 Hz 的激光雷达点云" in context.text
    assert "本次作答" in context.text or "<submission>" in context.text
    assert "丢帧但不拖慢发布" in context.text   # explanation
    assert '"a"' in context.text               # learner response
    assert "正确答案" in context.text


def test_context_lists_rubric_dimensions() -> None:
    context = build_review_context(PACK, submission("EX-QOS-005"))
    assert context.dimensions == ["机制", "场景"]
    assert "机制" in context.text


def test_choice_exercise_has_no_dimensions() -> None:
    assert build_review_context(PACK, submission()).dimensions == []


def test_system_prompt_requires_json_and_verdict() -> None:
    from testbridge.tutor.review import REVIEW_SYSTEM_PROMPT

    assert "JSON" in REVIEW_SYSTEM_PROMPT
    assert "verdict" in REVIEW_SYSTEM_PROMPT
    assert "suggested_score" in REVIEW_SYSTEM_PROMPT


def test_parse_valid_review() -> None:
    raw = (
        '{"verdict": "partial", "explanation": "方向和结论对，但漏了重传代价。", '
        '"strengths": ["选对了可靠性方向"], "gaps": ["没有提到重传会拖慢发布"], '
        '"rubric": [{"dimension": "机制", "met": true, "comment": "对"}, '
        '{"dimension": "场景", "met": false, "comment": "缺一个反例"}], '
        '"suggested_score": 0.5}'
    )
    review = parse_review(raw, ["机制", "场景"])
    assert review.verdict == "partial"
    assert review.strengths == ["选对了可靠性方向"]
    assert review.gaps == ["没有提到重传会拖慢发布"]
    assert [(item.dimension, item.met) for item in review.rubric] == [
        ("机制", True), ("场景", False),
    ]
    assert review.suggested_score == 0.5


def test_parse_drops_unknown_dimensions_and_orders_by_prompt() -> None:
    raw = (
        '{"verdict": "correct", "explanation": "x", '
        '"rubric": [{"dimension": "场景", "met": true, "comment": ""}, '
        '{"dimension": "机制", "met": true, "comment": ""}, '
        '{"dimension": "凭空造的", "met": true, "comment": ""}]}'
    )
    review = parse_review(raw, ["机制", "场景"])
    assert [item.dimension for item in review.rubric] == ["机制", "场景"]


def test_parse_clamps_score_and_requires_rubric() -> None:
    assert parse_review(
        '{"verdict": "correct", "explanation": "x", "suggested_score": 3}',
        ["机制"],
    ).suggested_score == 1.0
    assert parse_review(
        '{"verdict": "correct", "explanation": "x", "suggested_score": 0.5}', []
    ).suggested_score is None


def test_parse_invalid_json_falls_back_to_text() -> None:
    review = parse_review("模型直接写了一句话", ["机制"])
    assert review.explanation == "模型直接写了一句话"
    assert review.verdict == "partial"
    assert review.suggested_score is None
    assert review.rubric == []


def test_parse_caps_strengths_and_gaps() -> None:
    raw = (
        '{"explanation": "x", "strengths": ["a", "b", "c", "d"], '
        '"gaps": ["1", "2", "3", "4"]}'
    )
    review = parse_review(raw, [])
    assert len(review.strengths) == 3
    assert len(review.gaps) == 3
