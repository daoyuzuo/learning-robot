import shutil
from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.contract.models import Exercise
from testbridge.lesson.renderer import render_exercise_form, render_lesson

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"
PROMPT = 'Use <tag> & "quotes" \\d+'
ESCAPED_PROMPT = "Use &lt;tag&gt; &amp; &quot;quotes&quot; \\d+"


def _copy_pack(tmp_path: Path) -> Path:
    pack_dir = tmp_path / "pack"
    shutil.copytree(FIXTURE, pack_dir)
    return pack_dir


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


def test_render_handles_backslashes_in_prompt(tmp_path: Path) -> None:
    pack_dir = _copy_pack(tmp_path)
    (pack_dir / "exercises.yaml").write_text(
        "schema: tb/1\n"
        "exercises:\n"
        "  - id: EX-ONE\n"
        "    type: single_choice\n"
        "    concepts: [c-one]\n"
        "    level: L1\n"
        '    prompt: "Match \\\\d+ in C:\\\\Users and trailing \\\\"\n'
        "    options:\n"
        "      - {id: a, text: A}\n"
        "      - {id: b, text: B}\n"
        "    answer: a\n",
        encoding="utf-8",
    )
    view = render_lesson(load_pack(pack_dir), "L-ONE")
    assert "Match \\d+ in C:\\Users and trailing \\" in view.body_html


def test_widget_discovery_ignores_escaped_markup(tmp_path: Path) -> None:
    pack_dir = _copy_pack(tmp_path)
    lesson = pack_dir / "modules" / "M01" / "lessons" / "L-ONE.html"
    lesson.write_text(
        lesson.read_text(encoding="utf-8").replace(
            "<p>This is a demo.</p>",
            '<p>This is a demo.</p>'
            '<code>&lt;div data-tb-widget="W-NOPE"&gt;&lt;/div&gt;</code>',
        ),
        encoding="utf-8",
    )
    view = render_lesson(load_pack(pack_dir), "L-ONE")
    assert [item.widget.id for item in view.widgets] == ["W-ONE"]
    assert 'data-widget-id="W-ONE"' in view.body_html


def test_widget_template_is_sanitized(tmp_path: Path) -> None:
    pack_dir = _copy_pack(tmp_path)
    (pack_dir / "assets" / "widgets" / "demo.svg").write_text(
        '<svg viewBox="0 0 100 40" xmlns="http://www.w3.org/2000/svg">'
        '<a xlink:href="javascript:alert(1)"><text x="5" y="20">x</text></a>'
        "</svg>",
        encoding="utf-8",
    )
    view = render_lesson(load_pack(pack_dir), "L-ONE")
    assert "tb-widget-canvas" in view.body_html
    assert "xlink:href" not in view.body_html
    assert "javascript:" not in view.body_html


def test_render_single_choice_form() -> None:
    exercise = Exercise(
        id="EX-SINGLE",
        type="single_choice",
        concepts=["c-one"],
        level="L1",
        prompt=PROMPT,
        options=[{"id": "a", "text": "A & B"}, {"id": "b", "text": "B"}],
        answer="a",
    )
    form = render_exercise_form(exercise)
    assert 'data-exercise-type="single_choice"' in form
    assert 'type="radio" name="answer"' in form
    assert "A &amp; B" in form
    assert ESCAPED_PROMPT in form
    assert "<tag>" not in form


def test_render_multi_choice_form() -> None:
    exercise = Exercise(
        id="EX-MULTI",
        type="multi_choice",
        concepts=["c-one"],
        level="L1",
        prompt=PROMPT,
        options=[{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        answer=["a", "b"],
    )
    form = render_exercise_form(exercise)
    assert 'data-exercise-type="multi_choice"' in form
    assert 'type="checkbox" name="answer"' in form
    assert ESCAPED_PROMPT in form


def test_render_short_answer_form() -> None:
    exercise = Exercise(
        id="EX-SHORT",
        type="short_answer",
        concepts=["c-one"],
        level="L1",
        prompt=PROMPT,
        answer={"accepted": ["answer"], "min_hits": 1},
        rubric=[{"dimension": "accuracy", "weight": 1.0, "criteria": "Correct"}],
    )
    form = render_exercise_form(exercise)
    assert 'data-exercise-type="short_answer"' in form
    assert 'name="answer"' in form
    assert "<textarea" in form
    assert ESCAPED_PROMPT in form


def test_render_self_assess_form() -> None:
    exercise = Exercise(
        id="EX-SELF",
        type="self_assess",
        concepts=["c-one"],
        level="L1",
        prompt=PROMPT,
        rubric=[{"dimension": "accuracy", "weight": 1.0, "criteria": "Correct"}],
    )
    form = render_exercise_form(exercise)
    assert 'data-exercise-type="self_assess"' in form
    assert 'type="checkbox" name="checked"' in form
    assert ESCAPED_PROMPT in form


def test_render_artifact_form() -> None:
    exercise = Exercise(
        id="EX-ARTIFACT",
        type="artifact",
        concepts=["c-one"],
        level="L1",
        prompt=PROMPT,
        artifact={"accept": [".log"], "max_size_mb": 1},
        rubric=[{"dimension": "accuracy", "weight": 1.0, "criteria": "Correct"}],
    )
    form = render_exercise_form(exercise)
    assert 'data-exercise-type="artifact"' in form
    assert 'name="path"' in form
    assert 'name="notes"' in form
    assert 'type="checkbox" name="checked"' in form
    assert ESCAPED_PROMPT in form
