import json
from pathlib import Path

import pytest
import yaml

from testbridge.studio.lessons import LessonError, parse_lesson_json, write_lesson
from testbridge.studio.outline import LessonPlan
from testbridge.studio.store import DraftStore

LESSON = LessonPlan("L-EXEC-001", "单线程执行器", 20, ["说明调度顺序"], [])

PAYLOAD = {
    "manifest": {"title": "单线程执行器", "minutes": 20, "objectives": ["说明调度顺序"]},
    "html": '<article class="tb-lesson"><h1>单线程执行器</h1>'
            '<section><p>正文</p></section>'
            '<div data-tb-exercise="EX-1"></div></article>',
    "exercises": [{
        "id": "EX-1", "type": "single_choice", "concepts": ["executor-basics"],
        "level": "L2", "prompt": "哪个是单线程？",
        "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        "answer": "a", "difficulty": 2,
    }],
    "resources": [{
        "id": "DOC-1", "title": "Executors", "url": "https://docs.ros.org/x",
        "type": "official-doc", "trust": "A", "license": "Apache-2.0",
        "last_verified": "2026-10-25", "coverage": ["executor-basics"],
        "why": "官方说明",
    }],
}


def setup(tmp_path: Path) -> DraftStore:
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id="demo", topic="t", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    store.write("demo", "modules/M01/module.yaml", yaml.safe_dump({
        "schema": "tb/1", "id": "M01", "title": "M", "priority": "P1",
        "concepts": ["executor-basics"], "lessons": ["L-EXEC-001"], "order": 1,
    }, allow_unicode=True, sort_keys=False))
    return store


def test_parse_rejects_unknown_concept() -> None:
    with pytest.raises(LessonError):
        parse_lesson_json(json.dumps(PAYLOAD), LESSON, {"other-concept"})


def test_parse_rejects_script_in_html() -> None:
    broken = {**PAYLOAD, "html": "<article><script>x</script></article>"}
    with pytest.raises(LessonError):
        parse_lesson_json(json.dumps(broken), LESSON, {"executor-basics"})


def test_write_lesson_creates_files_and_merges_yaml(tmp_path: Path) -> None:
    store = setup(tmp_path)
    output = parse_lesson_json(json.dumps(PAYLOAD), LESSON, {"executor-basics"})

    write_lesson(store, "demo", LESSON, output)

    lesson_html = store.read("demo", "modules/M01/lessons/L-EXEC-001.html")
    assert '"id": "L-EXEC-001"' in lesson_html
    exercises = yaml.safe_load(store.read("demo", "exercises.yaml"))
    assert exercises["exercises"][0]["id"] == "EX-1"
    resources = yaml.safe_load(store.read("demo", "resources.yaml"))
    assert resources["resources"][0]["id"] == "DOC-1"


def test_duplicate_exercise_id_is_rejected(tmp_path: Path) -> None:
    store = setup(tmp_path)
    output = parse_lesson_json(json.dumps(PAYLOAD), LESSON, {"executor-basics"})
    write_lesson(store, "demo", LESSON, output)

    with pytest.raises(LessonError):
        write_lesson(store, "demo", LESSON, output)


def test_low_trust_resource_is_rejected() -> None:
    payload = {**PAYLOAD, "resources": [{**PAYLOAD["resources"][0], "trust": "C"}]}
    with pytest.raises(LessonError):
        parse_lesson_json(json.dumps(payload), LESSON, {"executor-basics"})


def test_write_lesson_uses_module_id(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(draft_id="demo", topic="t", level="L2",
                 lesson_count=2, searches_per_lesson=5,
                 model="m", prompt_version="studio/1")
    store.write("demo", "modules/M02/module.yaml", yaml.safe_dump({
        "schema": "tb/1", "id": "M02", "title": "M2", "priority": "P1",
        "concepts": ["executor-basics"], "lessons": ["L-EXEC-001"], "order": 2,
    }, allow_unicode=True, sort_keys=False))
    lesson = LessonPlan("L-EXEC-001", "课", 20, ["o"], [],
                        module_id="M02", concepts=["executor-basics"])
    output = parse_lesson_json(json.dumps(PAYLOAD), lesson, {"executor-basics"})

    write_lesson(store, "demo", lesson, output)

    assert store.read("demo", "modules/M02/lessons/L-EXEC-001.html")
    manifest = yaml.safe_load(
        store.read("demo", "modules/M02/lessons/L-EXEC-001.html")
        .split("</script>")[0]
        .split(">", 1)[1]
    )
    assert manifest["module"] == "M02"


def test_replace_removes_old_ids(tmp_path: Path) -> None:
    store = setup(tmp_path)
    output = parse_lesson_json(json.dumps(PAYLOAD), LESSON, {"executor-basics"})
    write_lesson(store, "demo", LESSON, output)

    replacement = {
        **PAYLOAD,
        "html": '<article class="tb-lesson"><div data-tb-exercise="EX-2"></div></article>',
        "exercises": [{**PAYLOAD["exercises"][0], "id": "EX-2"}],
        "resources": [{**PAYLOAD["resources"][0], "id": "DOC-2"}],
    }
    new_output = parse_lesson_json(
        json.dumps(replacement), LESSON, {"executor-basics"}
    )

    write_lesson(store, "demo", LESSON, new_output, replace=True)

    exercises = yaml.safe_load(store.read("demo", "exercises.yaml"))["exercises"]
    resources = yaml.safe_load(store.read("demo", "resources.yaml"))["resources"]
    assert [item["id"] for item in exercises] == ["EX-2"]
    assert [item["id"] for item in resources] == ["DOC-2"]


def test_replace_finds_lesson_after_module_move(tmp_path: Path) -> None:
    store = setup(tmp_path)
    write_lesson(
        store, "demo", LESSON,
        parse_lesson_json(json.dumps(PAYLOAD), LESSON, {"executor-basics"}),
    )
    store.write("demo", "modules/M02/module.yaml", yaml.safe_dump({
        "schema": "tb/1", "id": "M02", "title": "M2", "priority": "P1",
        "concepts": ["executor-basics"], "lessons": ["L-EXEC-001"], "order": 2,
    }, allow_unicode=True, sort_keys=False))
    moved = LessonPlan("L-EXEC-001", "课", 20, ["o"], [],
                       module_id="M02", concepts=["executor-basics"])
    replacement = {
        **PAYLOAD,
        "html": '<article class="tb-lesson"><div data-tb-exercise="EX-M2"></div></article>',
        "exercises": [{**PAYLOAD["exercises"][0], "id": "EX-M2"}],
        "resources": [{**PAYLOAD["resources"][0], "id": "DOC-M2"}],
    }

    write_lesson(
        store, "demo", moved,
        parse_lesson_json(json.dumps(replacement), moved, {"executor-basics"}),
        replace=True,
    )

    exercises = yaml.safe_load(store.read("demo", "exercises.yaml"))["exercises"]
    resources = yaml.safe_load(store.read("demo", "resources.yaml"))["resources"]
    assert [item["id"] for item in exercises] == ["EX-M2"]
    assert [item["id"] for item in resources] == ["DOC-M2"]
    assert store.read("demo", "modules/M01/lessons/L-EXEC-001.html")


def test_replace_still_rejects_other_lessons_ids(tmp_path: Path) -> None:
    store = setup(tmp_path)
    write_lesson(
        store, "demo", LESSON,
        parse_lesson_json(json.dumps(PAYLOAD), LESSON, {"executor-basics"}),
    )
    second = LessonPlan("L-EXEC-002", "第二课", 20, ["o"], [],
                        concepts=["executor-basics"])
    second_payload = {
        **PAYLOAD,
        "html": '<article class="tb-lesson"><div data-tb-exercise="EX-2"></div></article>',
        "exercises": [{**PAYLOAD["exercises"][0], "id": "EX-2"}],
        "resources": [{**PAYLOAD["resources"][0], "id": "DOC-2"}],
    }
    write_lesson(
        store, "demo", second,
        parse_lesson_json(json.dumps(second_payload), second, {"executor-basics"}),
    )
    clash = {
        **PAYLOAD,
        "exercises": [{**PAYLOAD["exercises"][0], "id": "EX-2"}],
    }

    with pytest.raises(LessonError):
        write_lesson(
            store, "demo", LESSON,
            parse_lesson_json(json.dumps(clash), LESSON, {"executor-basics"}),
            replace=True,
        )


def test_manifest_concepts_prefer_lesson_plan(tmp_path: Path) -> None:
    store = setup(tmp_path)
    lesson = LessonPlan("L-EXEC-001", "课", 20, ["o"], [],
                        concepts=["plan-a", "plan-b"])
    output = parse_lesson_json(json.dumps(PAYLOAD), lesson, {"executor-basics"})

    write_lesson(store, "demo", lesson, output)

    manifest = yaml.safe_load(
        store.read("demo", "modules/M01/lessons/L-EXEC-001.html")
        .split("</script>")[0]
        .split(">", 1)[1]
    )
    assert manifest["concepts"] == ["plan-a", "plan-b"]


def _payload(**resource_overrides) -> str:
    resource = {**PAYLOAD["resources"][0], **resource_overrides}
    return json.dumps({**PAYLOAD, "resources": [resource]})


def test_required_c_is_rejected() -> None:
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload(trust="C"), LESSON, {"executor-basics"}
        )


def test_supplementary_c_is_allowed() -> None:
    output = parse_lesson_json(
        _payload(trust="C", role="supplementary"), LESSON, {"executor-basics"}
    )
    assert output.resources[0]["role"] == "supplementary"
    assert output.resources[0]["trust"] == "C"


def test_d_trust_is_rejected_for_supplementary() -> None:
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload(trust="D", role="supplementary"),
            LESSON, {"executor-basics"},
        )


def test_last_verified_is_cleared_without_a_check() -> None:
    output = parse_lesson_json(
        _payload(), LESSON, {"executor-basics"}
    )
    assert output.resources[0]["last_verified"] == ""


def test_last_verified_is_set_for_checked_url() -> None:
    output = parse_lesson_json(
        _payload(), LESSON, {"executor-basics"},
        usable_urls={"https://docs.ros.org/x"},
    )
    assert output.resources[0]["last_verified"]


def test_required_must_pass_preflight() -> None:
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload(), LESSON, {"executor-basics"},
            usable_urls={"https://other.example"},
        )


def test_missing_kind_is_derived_from_type() -> None:
    output = parse_lesson_json(
        _payload(type="paper"), LESSON, {"executor-basics"}
    )
    assert output.resources[0]["kind"] == "paper"


def test_cross_lesson_id_collisions_are_namespaced(tmp_path: Path) -> None:
    store = setup(tmp_path)
    payload = {
        **PAYLOAD,
        "html": '<article class="tb-lesson">'
                '<div data-tb-exercise="EX-1"></div>'
                '<a data-tb-resource="DOC-1"></a></article>',
    }
    output = parse_lesson_json(json.dumps(payload), LESSON, {"executor-basics"})
    write_lesson(store, "demo", LESSON, output, namespace=True)

    second = LessonPlan(
        "L-EXEC-002", "课二", 20, ["o"], [],
        module_id="M01", concepts=["executor-basics"],
    )
    write_lesson(store, "demo", second, output, namespace=True)

    exercises = yaml.safe_load(store.read("demo", "exercises.yaml"))["exercises"]
    resources = yaml.safe_load(store.read("demo", "resources.yaml"))["resources"]
    assert [item["id"] for item in exercises] == ["EX-1", "L-EXEC-002-EX-1"]
    assert [item["id"] for item in resources] == ["DOC-1", "L-EXEC-002-DOC-1"]
    html = store.read("demo", "modules/M01/lessons/L-EXEC-002.html")
    assert 'data-tb-exercise="L-EXEC-002-EX-1"' in html
    assert 'data-tb-resource="L-EXEC-002-DOC-1"' in html


FIGURE = {
    "id": "FIG-1", "kind": "flow", "caption": "测试链路",
    "alt": "采集到判定的两步流程",
    "nodes": [{"id": "n1", "label": "采集"}, {"id": "n2", "label": "判定"}],
    "edges": [{"from": "n1", "to": "n2"}],
}


def _payload_with_figure(*, html: str | None = None, figures=None) -> str:
    body = html or (
        '<article class="tb-lesson"><h1>课</h1>'
        '<div data-tb-exercise="EX-1"></div>'
        '<div data-tb-figure="FIG-1"></div></article>'
    )
    return json.dumps({
        **PAYLOAD, "html": body, "figures": [FIGURE] if figures is None else figures,
    })


def test_lesson_embeds_inline_svg() -> None:
    output = parse_lesson_json(
        _payload_with_figure(), LESSON, {"executor-basics"}
    )
    assert output.figures[0]["id"] == "FIG-1"
    assert '<figure class="tb-figure">' in output.html
    assert "<svg " in output.html
    assert 'data-tb-figure="FIG-1"' not in output.html


def test_lesson_rejects_missing_mount() -> None:
    body = '<article class="tb-lesson"><div data-tb-exercise="EX-1"></div></article>'
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload_with_figure(html=body), LESSON, {"executor-basics"}
        )


def test_lesson_rejects_direct_svg() -> None:
    body = (
        '<article class="tb-lesson"><div data-tb-exercise="EX-1"></div>'
        '<svg viewBox="0 0 1 1"></svg></article>'
    )
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload_with_figure(html=body, figures=[]),
            LESSON, {"executor-basics"},
        )


def test_lesson_rejects_external_image() -> None:
    body = (
        '<article class="tb-lesson"><div data-tb-exercise="EX-1"></div>'
        '<img src="https://example.com/x.png" alt="x"></article>'
    )
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload_with_figure(html=body, figures=[]),
            LESSON, {"executor-basics"},
        )


def test_lesson_without_figures_still_works() -> None:
    output = parse_lesson_json(
        json.dumps({**PAYLOAD, "figures": []}), LESSON, {"executor-basics"}
    )
    assert output.figures == []


@pytest.mark.parametrize("src", [
    "https://example.com/x.png",
    "//example.com/x.png",
    "http&#58;//example.com/x.png",
    r"\\example.com/x.png",
    r"\/example.com/x.png",
    r"/\example.com/x.png",
])
def test_lesson_rejects_obfuscated_external_image(src: str) -> None:
    body = (
        '<article class="tb-lesson"><div data-tb-exercise="EX-1"></div>'
        f'<img src="{src}" alt="x"></article>'
    )
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload_with_figure(html=body, figures=[]),
            LESSON, {"executor-basics"},
        )


def test_lesson_rejects_unquoted_external_image() -> None:
    body = (
        '<article class="tb-lesson"><div data-tb-exercise="EX-1"></div>'
        '<img src=https://example.com/x.png alt=x></article>'
    )
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload_with_figure(html=body, figures=[]),
            LESSON, {"executor-basics"},
        )


def test_lesson_allows_relative_image() -> None:
    body = (
        '<article class="tb-lesson"><div data-tb-exercise="EX-1"></div>'
        '<img src="images/x.png" alt="x"></article>'
    )
    output = parse_lesson_json(
        _payload_with_figure(html=body, figures=[]),
        LESSON, {"executor-basics"},
    )
    assert 'src="images/x.png"' in output.html


@pytest.mark.parametrize("src", [r"images\\x.png", "images\\x.png"])
def test_lesson_allows_windows_style_relative_image(src: str) -> None:
    body = (
        '<article class="tb-lesson"><div data-tb-exercise="EX-1"></div>'
        f'<img src="{src}" alt="x"></article>'
    )
    output = parse_lesson_json(
        _payload_with_figure(html=body, figures=[]),
        LESSON, {"executor-basics"},
    )
    assert f'src="{src}"' in output.html
