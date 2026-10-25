import json
from pathlib import Path

import pytest
import yaml

from testbridge.studio.outline import (
    LessonPlan,
    ModulePlan,
    OutlineError,
    flatten_modules,
    lesson_plans,
    parse_outline_html,
    parse_outline_json,
    render_outline_html,
    save_outline_html,
    write_outline,
)
from testbridge.studio.store import DraftStore

SCHEMA = {
    "pack_title": "ROS 2 执行器",
    "concepts": [
        {"id": "executor-basics", "title": "执行器基础", "domain": "ros2",
         "target_level": "L2", "prerequisites": [], "weight": 1.0,
         "evidence_criteria": [{"id": "EV-1", "description": "能解释", "level": "L1"}]},
    ],
    "modules": [
        {"id": "M01", "title": "执行器基础", "concepts": ["executor-basics"],
         "lessons": [
             {"id": "L-EXEC-001", "title": "单线程执行器", "minutes": 20,
              "concepts": ["executor-basics"], "objectives": ["说明调度顺序"],
              "exercise_intents": ["选执行器"],
              "research_queries": ["ROS 2 executors"]},
             {"id": "L-EXEC-002", "title": "多线程执行器", "minutes": 25,
              "concepts": ["executor-basics"], "objectives": ["区分执行器"],
              "exercise_intents": ["判断并发"],
              "research_queries": ["ROS 2 multithreaded executor"]},
         ]},
        {"id": "M02", "title": "回调组", "concepts": ["executor-basics"],
         "lessons": [
             {"id": "L-CB-001", "title": "回调组基础", "minutes": 20,
              "concepts": ["executor-basics"], "objectives": ["说明回调组"],
              "exercise_intents": ["选回调组"],
              "research_queries": ["ROS 2 callback groups"]},
             {"id": "L-CB-002", "title": "互斥回调组", "minutes": 25,
              "concepts": ["executor-basics"], "objectives": ["区分回调组"],
              "exercise_intents": ["判断互斥"],
              "research_queries": ["ROS 2 mutually exclusive callback group"]},
         ]},
    ],
}

LEGACY_SCHEMA = {
    "module_title": "旧模块",
    "concepts": [{"id": "c-one", "title": "C", "domain": "d",
                  "target_level": "L2"}],
    "lessons": [
        {"id": "L-EXEC-001", "title": "课一", "minutes": 20,
         "objectives": ["o"], "research_queries": []},
        {"id": "L-EXEC-002", "title": "课二", "minutes": 20,
         "objectives": ["o"], "research_queries": []},
    ],
}


def test_parse_outline_json_validates_and_returns_modules() -> None:
    parsed = parse_outline_json(json.dumps(SCHEMA), 2, 2)
    assert parsed["pack_title"] == "ROS 2 执行器"
    assert len(parsed["modules"]) == 2
    assert len(lesson_plans(parsed)) == 4


def test_parse_outline_json_rejects_wrong_module_count() -> None:
    with pytest.raises(OutlineError):
        parse_outline_json(json.dumps(SCHEMA), 3, 2)


def test_parse_outline_json_rejects_wrong_lessons_per_module() -> None:
    with pytest.raises(OutlineError):
        parse_outline_json(json.dumps(SCHEMA), 2, 3)


def test_parse_outline_json_rejects_lesson_concept_outside_module() -> None:
    broken = json.loads(json.dumps(SCHEMA))
    broken["modules"][0]["lessons"][0]["concepts"] = ["other"]
    with pytest.raises(OutlineError):
        parse_outline_json(json.dumps(broken), 2, 2)


def test_parse_outline_json_rejects_string_objectives() -> None:
    broken = json.loads(json.dumps(SCHEMA))
    broken["modules"][0]["lessons"][0]["objectives"] = "说明调度顺序"
    with pytest.raises(OutlineError):
        parse_outline_json(json.dumps(broken), 2, 2)


def test_parse_outline_json_rejects_non_list_research_queries() -> None:
    broken = json.loads(json.dumps(SCHEMA))
    broken["modules"][0]["lessons"][0]["research_queries"] = "ROS 2 executors"
    with pytest.raises(OutlineError):
        parse_outline_json(json.dumps(broken), 2, 2)


def test_parse_outline_json_rejects_missing_prerequisite() -> None:
    broken = json.loads(json.dumps(SCHEMA))
    broken["concepts"][0]["prerequisites"] = ["nope"]
    with pytest.raises(OutlineError):
        parse_outline_json(json.dumps(broken), 2, 2)


def test_parse_outline_json_accepts_legacy_flat_schema() -> None:
    legacy = {
        "module_title": "旧模块",
        "concepts": [{"id": "c-one", "title": "C", "domain": "d",
                      "target_level": "L2"}],
        "lessons": [
            {"id": "L-1", "title": "课一", "minutes": 20,
             "objectives": ["o"], "research_queries": []},
            {"id": "L-2", "title": "课二", "minutes": 20,
             "objectives": ["o"], "research_queries": []},
        ],
    }
    parsed = parse_outline_json(json.dumps(legacy), 1, 2)
    assert parsed["modules"][0]["id"] == "M01"
    assert [plan.module_id for plan in lesson_plans(parsed)] == ["M01", "M01"]


def test_lesson_plans_carry_module_and_concepts() -> None:
    plans = lesson_plans(parse_outline_json(json.dumps(SCHEMA), 2, 2))

    assert [plan.module_id for plan in plans] == ["M01", "M01", "M02", "M02"]
    assert plans[0].concepts == ["executor-basics"]


def test_outline_html_round_trip_modules() -> None:
    lessons_a = [LessonPlan("L-1", "课一", 20, ["目标"], ["q1"],
                            module_id="M01", concepts=["c-one"])]
    lessons_b = [LessonPlan("L-2", "课二", 25, ["目标"], ["q2"],
                            module_id="M02", concepts=["c-one"])]
    modules = [
        ModulePlan("M01", "模块一", ["c-one"], lessons_a),
        ModulePlan("M02", "模块二", ["c-one"], lessons_b),
    ]

    parsed = parse_outline_html(render_outline_html("包", modules))

    assert [module.module_id for module in parsed] == ["M01", "M02"]
    assert parsed[1].lessons[0].minutes == 25
    assert parsed[0].lessons[0].concepts == ["c-one"]


def test_parse_outline_html_rejects_duplicate_module_ids() -> None:
    first = ModulePlan(
        "M01", "模块一", ["c-one"],
        [LessonPlan("L-1", "课一", 20, ["目标"], ["q1"], module_id="M01",
                    concepts=["c-one"])],
    )
    second = ModulePlan(
        "M01", "模块二", ["c-one"],
        [LessonPlan("L-2", "课二", 20, ["目标"], ["q2"], module_id="M01",
                    concepts=["c-one"])],
    )

    with pytest.raises(OutlineError):
        parse_outline_html(render_outline_html("包", [first, second]))


def test_legacy_flat_outline_html_falls_back_to_m01() -> None:
    html = (
        '<article class="tb-outline"><h1 class="tb-module-title">旧包</h1>'
        '<section class="tb-outline-lesson" id="L-1"><h2>课一</h2>'
        '<p class="tb-minutes">20</p><ul class="tb-objectives"><li>o</li></ul>'
        '<ul class="tb-queries"><li>q</li></ul></section></article>'
    )

    modules = parse_outline_html(html)

    assert len(modules) == 1
    assert modules[0].module_id == "M01"
    assert modules[0].concepts is None
    assert modules[0].lessons[0].lesson_id == "L-1"


def test_write_outline_creates_contract_files(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id="demo", topic="t", level="L2", lesson_count=2,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    parsed = parse_outline_json(json.dumps(LEGACY_SCHEMA), 1, 2)

    modules = write_outline(store, "demo", parsed)

    assert [module.module_id for module in modules] == ["M01"]
    assert [plan.lesson_id for plan in flatten_modules(modules)] == [
        "L-EXEC-001", "L-EXEC-002",
    ]
    module = yaml.safe_load(store.read("demo", "modules/M01/module.yaml"))
    assert module["lessons"] == ["L-EXEC-001", "L-EXEC-002"]


def test_write_outline_creates_module_files(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(draft_id="demo", topic="t", level="L2",
                 lesson_count=4, searches_per_lesson=5,
                 model="m", prompt_version="studio/1")
    parsed = parse_outline_json(json.dumps(SCHEMA), 2, 2)

    modules = write_outline(store, "demo", parsed)

    assert [module.module_id for module in modules] == ["M01", "M02"]
    assert store.read("demo", "modules/M01/module.yaml")
    assert store.read("demo", "modules/M02/module.yaml")
    assert "tb-outline-module" in store.read("demo", "outline.html")


def test_save_outline_rewrites_module_yaml_and_rekeys(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(draft_id="demo", topic="t", level="L2",
                 lesson_count=4, searches_per_lesson=5,
                 model="m", prompt_version="studio/1")
    write_outline(store, "demo", parse_outline_json(json.dumps(SCHEMA), 2, 2))
    html = store.read("demo", "outline.html").replace("L-CB-002", "L-CB-003")

    modules = save_outline_html(store, "demo", html)

    assert [plan.lesson_id for plan in flatten_modules(modules)][-1] == "L-CB-003"
    module = yaml.safe_load(store.read("demo", "modules/M02/module.yaml"))
    assert module["lessons"] == ["L-CB-001", "L-CB-003"]
    draft = store.load("demo")
    assert "L-CB-003" in draft["steps"]["lessons"]
    assert "L-CB-002" not in draft["steps"]["lessons"]


def test_save_outline_renames_removed_module_yaml(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(draft_id="demo", topic="t", level="L2",
                 lesson_count=4, searches_per_lesson=5,
                 model="m", prompt_version="studio/1")
    write_outline(store, "demo", parse_outline_json(json.dumps(SCHEMA), 2, 2))
    modules = parse_outline_html(store.read("demo", "outline.html"))

    save_outline_html(store, "demo", render_outline_html("ROS 2 执行器", modules[:1]))

    root = tmp_path / "drafts" / "demo" / "modules"
    assert (root / "M02" / "module.yaml.removed").is_file()
    assert not (root / "M02" / "module.yaml").exists()
    draft = store.load("demo")
    assert "L-CB-001" not in draft["steps"]["lessons"]


def test_save_outline_rejects_unknown_module_concept(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(draft_id="demo", topic="t", level="L2",
                 lesson_count=4, searches_per_lesson=5,
                 model="m", prompt_version="studio/1")
    write_outline(store, "demo", parse_outline_json(json.dumps(SCHEMA), 2, 2))
    html = store.read("demo", "outline.html").replace(
        '<ul class="tb-module-concepts"><li>executor-basics</li></ul>',
        '<ul class="tb-module-concepts"><li>unknown</li></ul>',
        1,
    )

    with pytest.raises(OutlineError):
        save_outline_html(store, "demo", html)


def test_write_outline_sanitizes_edited_html(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id="demo", topic="t", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    plan = LessonPlan("L-1", "课一", 10, ["目标"], [])
    module = ModulePlan("M01", "模块", None, [plan])
    html = render_outline_html("模块", [module]).replace(
        "</article>", "<script>alert(1)</script></article>"
    )

    store.write("demo", "outline.html", html)
    parsed = parse_outline_html(store.read("demo", "outline.html"))
    assert parsed[0].lessons[0].lesson_id == "L-1"
