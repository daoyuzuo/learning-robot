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
