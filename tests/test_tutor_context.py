from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.tutor.context import build_context

PACK = load_pack(Path(__file__).parents[1] / "content-packs" / "ros2-qos")


def test_context_includes_lesson_text_and_concepts() -> None:
    context = build_context(PACK, "L-QOS-002")
    assert context.lesson_id == "L-QOS-002"
    assert context.title == "QoS 策略与兼容性"
    assert "Request vs Offered" in context.text
    assert "DDS QoS 策略" in context.text
    assert context.resource_ids == ["DOC-QOS-SETTINGS", "DOC-DDS-SPEC"]


def test_context_includes_prompts_and_options() -> None:
    context = build_context(PACK, "L-QOS-002")
    assert "100 Hz 的激光雷达点云" in context.text
    assert "BEST_EFFORT" in context.text


def test_context_excludes_answers_explanations_and_hints() -> None:
    context = build_context(PACK, "L-QOS-002")
    assert "丢帧但不拖慢发布" not in context.text
    assert "重传意味着发布端要等确认" not in context.text
    assert "ros2 topic info" not in context.text


def test_headings_expose_section_titles() -> None:
    context = build_context(PACK, "L-QOS-002")
    assert "六类策略" in context.headings
    assert "兼容性：Request vs Offered" in context.headings
    assert context.headings[0] == "QoS 策略与兼容性"
