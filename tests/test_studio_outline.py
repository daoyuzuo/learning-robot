import json
from pathlib import Path

import pytest
import yaml

from testbridge.studio.outline import (
    LessonPlan,
    OutlineError,
    parse_outline_html,
    parse_outline_json,
    render_outline_html,
    write_outline,
)
from testbridge.studio.store import DraftStore

SCHEMA = {
    "module_title": "ROS 2 执行器",
    "concepts": [
        {"id": "executor-basics", "title": "执行器基础", "domain": "ros2",
         "target_level": "L2", "prerequisites": [], "weight": 1.0,
         "evidence_criteria": [{"id": "EV-1", "description": "能解释", "level": "L1"}]},
        {"id": "callback-groups", "title": "回调组", "domain": "ros2",
         "target_level": "L3", "prerequisites": ["executor-basics"], "weight": 1.0,
         "evidence_criteria": []},
    ],
    "lessons": [
        {"id": "L-EXEC-001", "title": "单线程执行器", "minutes": 20,
         "objectives": ["说明调度顺序"], "exercise_intents": ["选执行器"],
         "research_queries": ["ROS 2 executors"]},
        {"id": "L-EXEC-002", "title": "回调组", "minutes": 25,
         "objectives": ["区分回调组"], "exercise_intents": ["判断并发"],
         "research_queries": ["ROS 2 callback groups"]},
    ],
}


def test_parse_outline_json_validates_and_returns_dict() -> None:
    parsed = parse_outline_json(json.dumps(SCHEMA), lesson_count=2)
    assert parsed["module_title"] == "ROS 2 执行器"


def test_parse_outline_json_rejects_wrong_lesson_count() -> None:
    with pytest.raises(OutlineError):
        parse_outline_json(json.dumps(SCHEMA), lesson_count=3)


def test_parse_outline_json_rejects_missing_prerequisite() -> None:
    broken = {**SCHEMA, "concepts": [
        {**SCHEMA["concepts"][1], "prerequisites": ["nope"]},
    ]}
    with pytest.raises(OutlineError):
        parse_outline_json(json.dumps(broken), lesson_count=2)


def test_outline_html_round_trip() -> None:
    lessons = [
        LessonPlan("L-EXEC-001", "单线程执行器", 20, ["说明调度顺序"], ["ROS 2 executors"]),
        LessonPlan("L-EXEC-002", "回调组", 25, ["区分回调组"], ["ROS 2 callback groups"]),
    ]
    html = render_outline_html("ROS 2 执行器", lessons)

    parsed = parse_outline_html(html)

    assert [item.lesson_id for item in parsed] == ["L-EXEC-001", "L-EXEC-002"]
    assert parsed[1].minutes == 25
    assert parsed[0].objectives == ["说明调度顺序"]
    assert parsed[0].queries == ["ROS 2 executors"]


def test_write_outline_creates_contract_files(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id="demo", topic="ROS 2 执行器", level="L2", lesson_count=2,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    parsed = parse_outline_json(json.dumps(SCHEMA), lesson_count=2)

    plans = write_outline(store, "demo", parsed)

    assert [plan.lesson_id for plan in plans] == ["L-EXEC-001", "L-EXEC-002"]
    pack = yaml.safe_load(store.read("demo", "pack.yaml"))
    assert pack["id"] == "demo"
    concepts = yaml.safe_load(store.read("demo", "concepts.yaml"))
    assert len(concepts["concepts"]) == 2
    module = yaml.safe_load(store.read("demo", "modules/M01/module.yaml"))
    assert module["lessons"] == ["L-EXEC-001", "L-EXEC-002"]
    draft = store.load("demo")
    assert set(draft["steps"]["lessons"]) == {"L-EXEC-001", "L-EXEC-002"}
    assert "tb-outline" in store.read("demo", "outline.html")


def test_write_outline_sanitizes_edited_html(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id="demo", topic="t", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    plan = LessonPlan("L-1", "课一", 10, ["目标"], [])
    html = render_outline_html("模块", [plan]).replace(
        "</article>", "<script>alert(1)</script></article>"
    )

    store.write("demo", "outline.html", html)
    parsed = parse_outline_html(store.read("demo", "outline.html"))
    assert parsed[0].lesson_id == "L-1"
