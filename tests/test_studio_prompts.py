from testbridge.studio.outline import LessonPlan, render_lesson_outline
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
    prompt = render_outline_prompt("ROS 2", "L2", 2, 3)
    assert "模块数：2" in prompt
    assert "每模块课数：3" in prompt


def test_outline_prompt_caps_module_concepts_by_lesson_count() -> None:
    one = render_outline_prompt("ROS 2", "L2", 1, 1)
    two = render_outline_prompt("ROS 2", "L2", 1, 2)

    assert "每模块概念上限：2" in one
    assert "每模块概念上限：4" in two


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


def test_lesson_outline_scopes_to_target_lesson() -> None:
    plan = LessonPlan(
        "L-1", "课一", 20, ["目标"], ["query"],
        module_id="M01", concepts=["c-one"],
    )

    html = render_lesson_outline(plan)

    assert '<section class="tb-outline-lesson" id="L-1">' in html
    assert "c-one" in html
    assert "c-two" not in html


def test_lesson_system_restricts_exercises_to_lesson_concepts() -> None:
    assert "子集" in LESSON_SYSTEM


def test_lesson_prompt_requires_figures() -> None:
    assert "figures" in LESSON_SYSTEM
    assert "data-tb-figure" in LESSON_SYSTEM
    assert "caption" in LESSON_SYSTEM and "alt" in LESSON_SYSTEM


def test_outline_prompt_includes_guidance() -> None:
    prompt = render_outline_prompt(
        "ROS2", "L3", 2, 3, guidance=["多讲测试实操", "少讲论文"]
    )
    assert "写作方向" in prompt
    assert "多讲测试实操" in prompt
    assert "少讲论文" in prompt


def test_lesson_prompt_includes_guidance() -> None:
    prompt = render_lesson_prompt(
        "<article>x</article>", "概念", "资料", guidance=["多讲测试实操"]
    )
    assert "写作方向" in prompt
    assert "多讲测试实操" in prompt


def test_guidance_is_truncated_and_limited() -> None:
    prompt = render_outline_prompt(
        "t", "L2", 1, 1, guidance=["长" * 200] * 8
    )
    assert len(prompt) < 2000
    block = prompt.split("<guidance>")[1]
    assert "长" * 80 in block
    assert "长" * 81 not in block
    assert block.count("- ") == 5


def test_prompt_without_guidance_has_no_block() -> None:
    assert "<guidance>" not in render_outline_prompt("t", "L2", 1, 1)
    assert "<guidance>" not in render_lesson_prompt("x", "概念", "资料")
