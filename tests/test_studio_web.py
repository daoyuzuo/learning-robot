import json
import warnings
from pathlib import Path

import yaml

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.contract.validator import validate_pack
from testbridge.studio.outline import (
    LessonPlan,
    ModulePlan,
    parse_outline_html,
    parse_outline_json,
    render_outline_html,
    write_outline,
)
from testbridge.studio.search import SearchHit
from testbridge.tutor.config import TutorConfig
from web.app import create_app

CONFIG = TutorConfig(
    base_url="https://api.example.com/v1", api_key="sk-test",
    model="deepseek-chat", timeout=5.0,
)

OUTLINE_JSON = """
{"module_title": "执行器", "concepts": [
 {"id": "executor-basics", "title": "执行器基础", "domain": "ros2",
  "target_level": "L2", "prerequisites": [], "weight": 1.0,
  "evidence_criteria": [{"id": "EV-1", "description": "能解释", "level": "L1"}]}],
 "lessons": [{"id": "L-EXEC-001", "title": "单线程执行器", "minutes": 20,
  "objectives": ["说明调度顺序"], "exercise_intents": ["选择题"],
  "research_queries": ["ROS 2 executors"]}]}
"""

MULTI_OUTLINE_JSON = json.dumps({
    "pack_title": "执行器 2",
    "concepts": [
        {"id": "executor-basics", "title": "执行器基础", "domain": "ros2",
         "target_level": "L2", "prerequisites": [], "weight": 1.0,
         "evidence_criteria": [{"id": "EV-1", "description": "能解释", "level": "L1"}]}],
    "modules": [
        {"id": "M01", "title": "执行器基础", "concepts": ["executor-basics"],
         "lessons": [
             {"id": "L-EXEC-001", "title": "单线程执行器", "minutes": 20,
              "concepts": ["executor-basics"], "objectives": ["说明调度顺序"],
              "exercise_intents": ["选择题"],
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
})

TWO_CONCEPT_OUTLINE_JSON = json.dumps({
    "pack_title": "双概念课",
    "concepts": [
        {"id": "executor-basics", "title": "执行器基础", "domain": "ros2",
         "target_level": "L2", "prerequisites": [], "weight": 1.0,
         "evidence_criteria": []},
        {"id": "c-two", "title": "概念二", "domain": "ros2",
         "target_level": "L2", "prerequisites": [], "weight": 1.0,
         "evidence_criteria": []},
    ],
    "modules": [
        {"id": "M01", "title": "模块一",
         "concepts": ["executor-basics", "c-two"],
         "lessons": [
             {"id": "L-EXEC-001", "title": "单线程执行器", "minutes": 20,
              "concepts": ["executor-basics"], "objectives": ["说明调度顺序"],
              "exercise_intents": ["选择题"],
              "research_queries": ["ROS 2 executors"]},
             {"id": "L-EXEC-002", "title": "概念二课", "minutes": 20,
              "concepts": ["c-two"], "objectives": ["理解概念二"],
              "exercise_intents": ["选择题"],
              "research_queries": ["concept two"]},
         ]},
    ],
})

LEGACY_TWO_LESSONS_JSON = json.dumps({
    "module_title": "执行器",
    "concepts": [
        {"id": "executor-basics", "title": "执行器基础", "domain": "ros2",
         "target_level": "L2", "prerequisites": [], "weight": 1.0,
         "evidence_criteria": [{"id": "EV-1", "description": "能解释", "level": "L1"}]}],
    "lessons": [
        {"id": "L-EXEC-001", "title": "单线程执行器", "minutes": 20,
         "objectives": ["说明调度顺序"], "exercise_intents": ["选择题"],
         "research_queries": ["ROS 2 executors"]},
        {"id": "L-EXEC-002", "title": "多线程执行器", "minutes": 25,
         "objectives": ["区分执行器"], "exercise_intents": ["判断并发"],
         "research_queries": ["ROS 2 multithreaded executor"]},
    ],
})

LESSON_JSON = (
    '{"manifest": {"title": "单线程执行器", "minutes": 20, '
    '"objectives": ["说明调度顺序"]}, '
    '"html": "<article class=\\"tb-lesson\\"><h1>课</h1>'
    '<div data-tb-exercise=\\"EX-1\\"></div>'
    '<div data-tb-exercise=\\"EX-2\\"></div>'
    '<div data-tb-exercise=\\"EX-3\\"></div></article>", '
    '"exercises": ['
    '{"id": "EX-1", "type": "single_choice", '
    '"concepts": ["executor-basics"], "level": "L2", "prompt": "选一个", '
    '"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}], '
    '"answer": "a"}, '
    '{"id": "EX-2", "type": "multi_choice", '
    '"concepts": ["executor-basics"], "level": "L2", "prompt": "多选", '
    '"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}], '
    '"answer": ["a"]}, '
    '{"id": "EX-3", "type": "short_answer", '
    '"concepts": ["executor-basics"], "level": "L2", "prompt": "简答", '
    '"answer": {"accepted": ["x"], "min_hits": 1}, '
    '"rubric": [{"dimension": "d", "weight": 1.0, "criteria": "c"}]}'
    '], '
    '"resources": [{"id": "DOC-1", "title": "Executors", '
    '"url": "https://docs.ros.org/x", "type": "official-doc", '
    '"trust": "A", "license": "Apache-2.0", '
    '"last_verified": "2026-10-25", "coverage": ["executor-basics"], '
    '"why": "官方"}]}'
)


class FakeLlm:
    def __init__(self, outline_json: str = OUTLINE_JSON) -> None:
        self.calls = 0
        self.outline_json = outline_json
        self.outline_prompts: list[str] = []
        self.lesson_prompts: list[str] = []

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if "课程设计师" in system:
            self.outline_prompts.append(user)
            return self.outline_json
        self.lesson_prompts.append(user)
        return LESSON_JSON


class FakeSearch:
    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        return [SearchHit(
            title="Executors", url="https://docs.ros.org/x", snippet="",
            summary="", content="", authority=3,
        )]

    def fetch(self, url: str) -> str:
        return ""


SAMPLE = Path(__file__).parents[1] / "content-packs" / "ros2-qos"


def make_app(tmp_path: Path, llm: FakeLlm | None = None) -> TestClient:
    return TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts",
        studio_packs=tmp_path / "packs",
        studio_llm=llm or FakeLlm(),
        studio_search=FakeSearch(),
        studio_config=CONFIG,
    ))


def create_draft(app: TestClient, draft_id: str = "demo") -> None:
    response = app.post("/studio", data={
        "draft_id": draft_id, "topic": "ROS 2 执行器", "level": "L2",
        "lesson_count": "1", "searches_per_lesson": "5",
    }, follow_redirects=False)
    assert response.status_code == 303


def seed_multi_draft(app: TestClient):
    """Seed a 2-module draft and write its 2x2 outline directly."""
    store = app.app.state.studio_store
    store.create(
        draft_id="multi", topic="t", level="L2",
        module_count=2, lessons_per_module=2,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    parsed = parse_outline_json(MULTI_OUTLINE_JSON, 2, 2)
    write_outline(store, "multi", parsed)
    return store


def test_studio_list_page_renders(tmp_path: Path) -> None:
    assert "新建草稿" in make_app(tmp_path).get("/studio").text


def test_studio_list_offers_module_fields(tmp_path: Path) -> None:
    page = make_app(tmp_path).get("/studio").text
    assert 'name="module_count"' in page
    assert 'name="lessons_per_module"' in page
    assert 'name="lesson_count"' not in page


def test_create_draft_runs_outline(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    create_draft(app)
    draft = app.app.state.studio_store.load("demo")
    assert draft["steps"]["outline"]["status"] == "done"
    assert (tmp_path / "drafts" / "demo" / "outline.html").is_file()
    assert draft["module_count"] == 1
    assert draft["lessons_per_module"] == 1


def test_create_draft_with_module_counts(tmp_path: Path) -> None:
    llm = FakeLlm(MULTI_OUTLINE_JSON)
    app = make_app(tmp_path, llm)
    response = app.post("/studio", data={
        "draft_id": "multi", "topic": "t", "level": "L2",
        "module_count": "2", "lessons_per_module": "2",
        "searches_per_lesson": "5",
    }, follow_redirects=False)

    assert response.status_code == 303
    draft = app.app.state.studio_store.load("multi")
    assert draft["module_count"] == 2
    assert draft["lessons_per_module"] == 2
    assert draft["lesson_count"] == 4
    assert draft["steps"]["outline"]["status"] == "done"
    assert "模块数：2" in llm.outline_prompts[-1]
    assert "每模块课数：2" in llm.outline_prompts[-1]
    page = app.get("/studio/multi")
    assert "2 模块" in page.text
    assert "4 课" in page.text


def test_outline_uses_legacy_lesson_count_when_module_fields_missing(
    tmp_path: Path,
) -> None:
    llm = FakeLlm(LEGACY_TWO_LESSONS_JSON)
    app = make_app(tmp_path, llm)
    store = app.app.state.studio_store
    draft = store.create(
        draft_id="legacy", topic="t", level="L2", lesson_count=2,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    draft.pop("module_count")
    draft.pop("lessons_per_module")
    store.save(draft)

    response = app.post("/api/studio/legacy/outline")

    assert response.status_code == 200, response.text
    assert "模块数：1" in llm.outline_prompts[-1]
    assert "每模块课数：2" in llm.outline_prompts[-1]


def test_create_rejects_inconsistent_counts(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    response = app.post("/studio", data={
        "draft_id": "bad", "topic": "t", "level": "L2",
        "module_count": "2", "lessons_per_module": "2", "lesson_count": "3",
        "searches_per_lesson": "5",
    }, follow_redirects=False)

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_lesson_count"


def test_draft_page_renders_steps(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    create_draft(app)
    page = app.get("/studio/demo")
    assert page.status_code == 200
    assert "L-EXEC-001" in page.text
    assert "开始调研" in page.text


def test_status_endpoint_returns_steps(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    create_draft(app)
    payload = app.get("/api/studio/demo").json()
    assert payload["id"] == "demo"
    assert payload["steps"]["outline"]["status"] == "done"


def test_draft_page_groups_lessons_by_module(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed_multi_draft(app)

    page = app.get("/studio/multi")

    assert page.status_code == 200
    assert "M01 · 执行器基础" in page.text
    assert "M02 · 回调组" in page.text
    assert page.text.index("M01 · 执行器基础") < page.text.index("M02 · 回调组")


def test_save_outline_updates_module_files_and_steps(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    store = seed_multi_draft(app)
    html = store.read("multi", "outline.html").replace("L-CB-002", "L-CB-003")

    response = app.put("/api/studio/multi/outline", json={"html": html})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["modules"] == ["M01", "M02"]
    assert payload["lessons"][-1] == "L-CB-003"
    module = yaml.safe_load(store.read("multi", "modules/M02/module.yaml"))
    assert module["lessons"] == ["L-CB-001", "L-CB-003"]
    assert "L-CB-003" in store.load("multi")["steps"]["lessons"]
    assert "L-CB-002" not in store.load("multi")["steps"]["lessons"]


def test_save_outline_updates_actual_counts_and_page_meta(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    store = seed_multi_draft(app)
    modules = parse_outline_html(store.read("multi", "outline.html"))
    third = ModulePlan("M03", "事件驱动", ["executor-basics"], [
        LessonPlan("L-CB-003", "事件课", 20, ["目标"], ["q"],
                   module_id="M03", concepts=["executor-basics"]),
        LessonPlan("L-CB-004", "定时器课", 20, ["目标"], ["q"],
                   module_id="M03", concepts=["executor-basics"]),
    ])

    response = app.put("/api/studio/multi/outline", json={
        "html": render_outline_html("执行器 2", modules + [third]),
    })

    assert response.status_code == 200, response.text
    draft = store.load("multi")
    assert draft["module_count"] == 3
    assert draft["lesson_count"] == 6
    assert draft["lessons_per_module"] == 2
    page = app.get("/studio/multi").text
    assert "3 模块" in page
    assert "6 课" in page


def test_lesson_prompt_scoped_to_target_lesson_concepts(tmp_path: Path) -> None:
    llm = FakeLlm(TWO_CONCEPT_OUTLINE_JSON)
    app = make_app(tmp_path, llm)
    app.post("/studio", data={
        "draft_id": "scope", "topic": "双概念", "level": "L2",
        "module_count": "1", "lessons_per_module": "2",
        "searches_per_lesson": "5",
    }, follow_redirects=False)

    response = app.post(
        "/api/studio/scope/lessons", json={"lesson_id": "L-EXEC-001"}
    )

    assert response.status_code == 200, response.text
    prompt = llm.lesson_prompts[-1]
    assert "executor-basics" in prompt
    assert "c-two" not in prompt
    assert '<section class="tb-outline-lesson" id="L-EXEC-001">' in prompt
    assert "L-EXEC-002" not in prompt


def test_save_outline_requires_lesson_ids(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    create_draft(app)
    response = app.put("/api/studio/demo/outline", json={"html": "<article></article>"})
    assert response.status_code == 400


def test_full_flow_validates_and_promotes(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    create_draft(app)

    research = app.post(
        "/api/studio/demo/research", json={"lesson_id": "L-EXEC-001"}
    )
    assert research.status_code == 200
    lesson = app.post("/api/studio/demo/lessons", json={"lesson_id": "L-EXEC-001"})
    assert lesson.status_code == 200

    draft = app.app.state.studio_store.load("demo")
    entry = draft["steps"]["lessons"]["L-EXEC-001"]
    assert entry["prompt_version"] == "studio/2"
    assert entry["written_at"]

    validation = app.post("/api/studio/demo/validate", json={"skip_verify": True})
    assert validation.status_code == 200
    assert validation.json()["ok"] is True, validation.json()
    assert validation.json()["quality"]["score"] == 100

    promoted = app.post("/api/studio/demo/promote", json={"skip_verify": True})
    assert promoted.status_code == 200, promoted.text
    assert (tmp_path / "packs" / "demo" / "pack.yaml").is_file()
    assert validate_pack(tmp_path / "packs" / "demo").errors == []

    reloaded = app.get("/api/studio/demo").json()
    assert reloaded["steps"]["research"]["L-EXEC-001"]["status"] == "done"
    assert reloaded["steps"]["lessons"]["L-EXEC-001"]["status"] == "done"
    assert reloaded["steps"]["promote"]["status"] == "done"
