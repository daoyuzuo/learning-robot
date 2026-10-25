from testbridge.studio.prompts import (
    LESSON_SYSTEM,
    OUTLINE_SYSTEM,
    render_concepts_text,
    render_lesson_prompt,
    render_outline_prompt,
)


def test_lesson_prompt_documents_contract_fields() -> None:
    for token in (
        "concepts", "data-tb-exercise", "rubric", "coverage", "trust", "last_verified",
    ):
        assert token in LESSON_SYSTEM


def test_outline_prompt_asks_for_json() -> None:
    assert "JSON" in OUTLINE_SYSTEM
    assert "课程节数：3" in render_outline_prompt("ROS 2", "L2", 3)


def test_lesson_prompt_embeds_all_sections() -> None:
    prompt = render_lesson_prompt("<article>outline</article>", "- c1 概念", "{}")
    assert "<outline>" in prompt
    assert "<concepts>" in prompt
    assert "<research>" in prompt


def test_lesson_prompt_encodes_quality_gates() -> None:
    for token in ("至少 2 道", "target_level", "每个概念", "A/B", "不得为空"):
        assert token in LESSON_SYSTEM


def test_concepts_text_includes_target_levels() -> None:
    text = render_concepts_text(
        "L3", [{"id": "c-one", "title": "概念一", "target_level": "L2"}]
    )
    assert "课程目标级别：L3" in text
    assert "target_level=L2" in text
