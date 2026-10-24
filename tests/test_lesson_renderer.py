from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.lesson.renderer import render_lesson

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


def test_render_replaces_placeholders() -> None:
    pack = load_pack(FIXTURE)
    view = render_lesson(pack, "L-ONE")
    assert "tb-manifest" not in view.body_html
    assert 'form class="tb-exercise"' in view.body_html
    assert "data-exercise-id=\"EX-ONE\"" in view.body_html
    assert "tb-widget-canvas" in view.body_html
    assert "{{offset}}" in view.body_html


def test_render_resolves_refs() -> None:
    pack = load_pack(FIXTURE)
    view = render_lesson(pack, "L-ONE")
    assert view.module.id == "M01"
    assert [item.id for item in view.concepts] == ["c-one"]
    assert [item.id for item in view.exercises] == ["EX-ONE"]
    assert [item.id for item in view.resources] == ["DOC-ONE"]
    assert view.widgets[0].widget.id == "W-ONE"
    assert view.prev_lesson is None and view.next_lesson is None
