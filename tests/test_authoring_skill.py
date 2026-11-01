"""The authoring skill is a usable, self-contained contract reference."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / ".claude" / "skills" / "course-author"


def read(name: str) -> str:
    return (SKILL_DIR / name).read_text(encoding="utf-8")


def test_skill_has_frontmatter_and_core_workflow() -> None:
    text = read("SKILL.md")

    assert text.startswith("---\n")
    assert "name: course-author" in text
    assert "description:" in text
    for token in (
        "tb scaffold", "tb validate", "tb quality", "content-packs/",
        "WebSearch", "不要修改", "data-tb-exercise",
    ):
        assert token in text
    assert "没有 `/studio`" in text


def test_skill_references_are_present_and_useful() -> None:
    contract = read("references/content-contract.md")
    guide = read("references/authoring-guide.md")

    for token in (
        "tb-manifest", "data-tb-exercise", "single_choice", "short_answer",
        "resources.yaml", "concepts.yaml", "tb/1",
    ):
        assert token in contract
    for token in ("官方", "练习", "概念", "target_level", "学习证据"):
        assert token in guide


def test_skill_points_at_a_runnable_example() -> None:
    text = read("SKILL.md") + read("references/content-contract.md")
    assert "tests/fixtures/packs/sample-sensors" in text
