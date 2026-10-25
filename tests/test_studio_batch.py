"""Sequential batch jobs and single-lesson rewrite."""

import json
import threading
import time
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from testbridge.contract.validator import validate_pack
from testbridge.studio.outline import (
    ModulePlan,
    parse_outline_html,
    parse_outline_json,
    render_outline_html,
    write_outline,
)
from testbridge.studio.search import SearchHit
from testbridge.studio.search_router import SearchRoute
from testbridge.tutor.config import TutorConfig
from web.app import create_app

CONFIG = TutorConfig(
    base_url="https://api.example.com/v1", api_key="sk-test",
    model="deepseek-chat", timeout=5.0,
)

OUTLINE_JSON = json.dumps({
    "pack_title": "批量包",
    "concepts": [
        {"id": "c-one", "title": "概念一", "domain": "ros2",
         "target_level": "L2", "prerequisites": [], "weight": 1.0,
         "evidence_criteria": [
             {"id": "EV-1", "description": "能解释", "level": "L1"},
         ]},
    ],
    "modules": [
        {"id": "M01", "title": "模块一", "concepts": ["c-one"],
         "lessons": [
             {"id": "L-1", "title": "课一", "minutes": 20,
              "concepts": ["c-one"], "objectives": ["目标一"],
              "exercise_intents": ["选择题"],
              "research_queries": ["query one"]},
             {"id": "L-2", "title": "课二", "minutes": 20,
              "concepts": ["c-one"], "objectives": ["目标二"],
              "exercise_intents": ["选择题"],
              "research_queries": ["query two"]},
         ]},
    ],
})


MULTI_OUTLINE_JSON = json.dumps({
    "pack_title": "双模块包",
    "concepts": [
        {"id": "c-one", "title": "概念一", "domain": "ros2",
         "target_level": "L2", "prerequisites": [], "weight": 1.0,
         "evidence_criteria": [
             {"id": "EV-1", "description": "能解释", "level": "L1"},
         ]},
    ],
    "modules": [
        {"id": "M01", "title": "模块一", "concepts": ["c-one"],
         "lessons": [
             {"id": "L-1", "title": "课一", "minutes": 20,
              "concepts": ["c-one"], "objectives": ["目标一"],
              "exercise_intents": ["选择题"],
              "research_queries": ["query one"]},
             {"id": "L-2", "title": "课二", "minutes": 20,
              "concepts": ["c-one"], "objectives": ["目标二"],
              "exercise_intents": ["选择题"],
              "research_queries": ["query two"]},
         ]},
        {"id": "M02", "title": "模块二", "concepts": ["c-one"],
         "lessons": [
             {"id": "L-3", "title": "课三", "minutes": 20,
              "concepts": ["c-one"], "objectives": ["目标三"],
              "exercise_intents": ["选择题"],
              "research_queries": ["query three"]},
             {"id": "L-4", "title": "课四", "minutes": 20,
              "concepts": ["c-one"], "objectives": ["目标四"],
              "exercise_intents": ["选择题"],
              "research_queries": ["query four"]},
         ]},
    ],
})


def lesson_json(number: int) -> str:
    return json.dumps({
        "manifest": {"title": f"课{number}", "minutes": 20, "objectives": ["目标"]},
        "html": (
            '<article class="tb-lesson"><h1>课</h1>'
            f'<div data-tb-exercise="EX-{number}-1"></div>'
            f'<div data-tb-exercise="EX-{number}-2"></div>'
            f'<div data-tb-exercise="EX-{number}-3"></div>'
            "</article>"
        ),
        "exercises": [
            {"id": f"EX-{number}-1", "type": "single_choice",
             "concepts": ["c-one"], "level": "L2", "prompt": "选一个",
             "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
             "answer": "a"},
            {"id": f"EX-{number}-2", "type": "multi_choice",
             "concepts": ["c-one"], "level": "L2", "prompt": "多选",
             "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
             "answer": ["a"]},
            {"id": f"EX-{number}-3", "type": "short_answer",
             "concepts": ["c-one"], "level": "L2", "prompt": "简答",
             "answer": {"accepted": ["x"], "min_hits": 1},
             "rubric": [{"dimension": "d", "weight": 1.0, "criteria": "c"}]},
        ],
        "resources": [
            {"id": f"DOC-{number}", "title": "文档",
             "url": "https://docs.example/x", "type": "official-doc",
             "trust": "A", "license": "Apache-2.0",
             "last_verified": "2026-10-25", "coverage": ["c-one"],
             "why": "官方"},
        ],
    }, ensure_ascii=False)


class FakeLlm:
    """Outline response plus either fixed or per-call unique lesson output."""

    def __init__(
        self,
        *,
        fixed_ids: bool = False,
        fail_on_call: int | None = None,
        block: threading.Event | None = None,
        started: threading.Event | None = None,
        outline: str = OUTLINE_JSON,
    ) -> None:
        self.fixed_ids = fixed_ids
        self.fail_on_call = fail_on_call
        self.block = block
        self.started = started
        self.outline = outline
        self.lesson_calls = 0

    def complete(self, system: str, user: str) -> str:
        if "课程设计师" in system:
            if self.started is not None:
                self.started.set()
            if self.block is not None:
                self.block.wait(5)
            return self.outline
        self.lesson_calls += 1
        if self.fail_on_call == self.lesson_calls:
            raise RuntimeError("model down")
        number = 1 if self.fixed_ids else self.lesson_calls
        return lesson_json(number)


class FakeSearch:
    def __init__(
        self,
        *,
        block: threading.Event | None = None,
        started: threading.Event | None = None,
    ) -> None:
        self.block = block
        self.started = started
        self.queries: list[str] = []

    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        self.queries.append(query)
        if self.started is not None:
            self.started.set()
        if self.block is not None:
            self.block.wait(5)
        return [SearchHit(
            title="文档", url="https://docs.example/x", snippet="",
            summary="", content="", authority=3,
        )]

    def fetch(self, url: str) -> str:
        return ""


class FlakyRouteSearch(FakeSearch):
    """Fail routing for the first lesson, then succeed for the next one."""

    def __init__(self) -> None:
        super().__init__()
        self.routes = 0

    def route(self, *args, **kwargs) -> SearchRoute:
        self.routes += 1
        if self.routes == 1:
            raise RuntimeError("route down")
        return SearchRoute("custom", self)


SAMPLE = Path(__file__).parents[1] / "content-packs" / "ros2-qos"


def make_app(
    tmp_path: Path,
    *,
    llm: FakeLlm | None = None,
    search: FakeSearch | None = None,
    inline: bool = True,
) -> TestClient:
    return TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts",
        studio_packs=tmp_path / "packs",
        studio_llm=llm or FakeLlm(),
        studio_search=search or FakeSearch(),
        studio_config=CONFIG,
        studio_inline=inline,
    ))


def seed_draft(app: TestClient) -> None:
    store = app.app.state.studio_store
    store.create(
        draft_id="demo", topic="t", level="L2",
        module_count=1, lessons_per_module=2,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    write_outline(store, "demo", parse_outline_json(OUTLINE_JSON, 1, 2))


def wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def exercises(app: TestClient) -> list[dict]:
    store = app.app.state.studio_store
    data = yaml.safe_load(store.read("demo", "exercises.yaml"))
    return list(data.get("exercises") or [])


def test_batch_rejects_unknown_mode(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed_draft(app)

    response = app.post("/api/studio/demo/batch", json={"mode": "write"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_request"


def test_batch_research_runs_every_pending_lesson(tmp_path: Path) -> None:
    search = FakeSearch()
    app = make_app(tmp_path, search=search)
    seed_draft(app)

    response = app.post("/api/studio/demo/batch", json={"mode": "research"})

    assert response.status_code == 200, response.text
    assert response.json()["started"] == ["L-1", "L-2"]
    draft = app.app.state.studio_store.load("demo")
    assert draft["steps"]["batch"]["status"] == "done"
    assert draft["steps"]["batch"]["mode"] == "research"
    assert draft["steps"]["batch"]["done"] == 2
    assert draft["steps"]["batch"]["total"] == 2
    assert draft["steps"]["research"]["L-1"]["status"] == "done"
    assert draft["steps"]["research"]["L-2"]["status"] == "done"
    assert len(search.queries) == 8


def test_batch_returns_empty_when_nothing_is_pending(tmp_path: Path) -> None:
    search = FakeSearch()
    app = make_app(tmp_path, search=search)
    seed_draft(app)
    store = app.app.state.studio_store
    for lesson_id in ("L-1", "L-2"):
        store.set_step("demo", "research", status="done", lesson_id=lesson_id)

    response = app.post("/api/studio/demo/batch", json={"mode": "research"})

    assert response.status_code == 200
    assert response.json() == {"started": []}
    assert search.queries == []
    assert store.load("demo")["steps"]["batch"]["status"] == "pending"


def test_batch_empty_targets_conflicts_when_batch_is_running(
    tmp_path: Path,
) -> None:
    app = make_app(tmp_path)
    seed_draft(app)
    store = app.app.state.studio_store
    for lesson_id in ("L-1", "L-2"):
        store.set_step("demo", "research", status="done", lesson_id=lesson_id)
    store.set_step("demo", "batch", status="running", extra={
        "mode": "research", "done": 1, "total": 2,
    })

    response = app.post("/api/studio/demo/batch", json={"mode": "research"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "step_running"


def test_batch_research_continues_after_one_lesson_fails(tmp_path: Path) -> None:
    search = FlakyRouteSearch()
    app = make_app(tmp_path, search=search)
    seed_draft(app)

    response = app.post("/api/studio/demo/batch", json={"mode": "research"})

    assert response.status_code == 200, response.text
    assert response.json()["started"] == ["L-1", "L-2"]
    draft = app.app.state.studio_store.load("demo")
    assert draft["steps"]["research"]["L-1"]["status"] == "failed"
    assert "route down" in draft["steps"]["research"]["L-1"]["error"]
    assert draft["steps"]["research"]["L-2"]["status"] == "done"
    assert draft["steps"]["batch"]["status"] == "failed"
    assert draft["steps"]["batch"]["error"] == "1 课失败"
    assert draft["steps"]["batch"]["done"] == 2
    assert draft["steps"]["batch"]["total"] == 2


def test_rewrite_requires_lesson_id(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed_draft(app)

    response = app.post("/api/studio/demo/lessons", json={"replace": True})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_request"


def test_batch_lessons_continues_after_failure(tmp_path: Path) -> None:
    llm = FakeLlm(fail_on_call=2)
    app = make_app(tmp_path, llm=llm)
    seed_draft(app)

    first = app.post("/api/studio/demo/batch", json={"mode": "lessons"})

    assert first.status_code == 200, first.text
    assert first.json()["started"] == ["L-1", "L-2"]
    draft = app.app.state.studio_store.load("demo")
    assert draft["steps"]["lessons"]["L-1"]["status"] == "done"
    assert draft["steps"]["lessons"]["L-2"]["status"] == "failed"
    assert "model down" in draft["steps"]["lessons"]["L-2"]["error"]
    assert draft["steps"]["batch"]["status"] == "failed"
    assert draft["steps"]["batch"]["error"] == "1 课失败"
    assert draft["steps"]["batch"]["done"] == 2
    assert draft["steps"]["batch"]["total"] == 2
    assert len(exercises(app)) == 3

    second = app.post("/api/studio/demo/batch", json={"mode": "lessons"})

    assert second.json()["started"] == ["L-2"]
    draft = app.app.state.studio_store.load("demo")
    assert draft["steps"]["lessons"]["L-2"]["status"] == "done"
    assert draft["steps"]["batch"]["status"] == "done"
    assert len(exercises(app)) == 6


def test_batch_lessons_rewrites_failed_lesson_with_replace(tmp_path: Path) -> None:
    llm = FakeLlm(fixed_ids=True)
    app = make_app(tmp_path, llm=llm)
    seed_draft(app)
    store = app.app.state.studio_store
    written = app.post(
        "/api/studio/demo/lessons", json={"lesson_id": "L-1"}
    )
    assert written.status_code == 200
    assert len(exercises(app)) == 3
    store.set_step("demo", "lessons", status="failed", lesson_id="L-1")
    store.set_step("demo", "lessons", status="done", lesson_id="L-2")

    response = app.post("/api/studio/demo/batch", json={"mode": "lessons"})

    assert response.status_code == 200, response.text
    assert response.json()["started"] == ["L-1"]
    draft = store.load("demo")
    assert draft["steps"]["lessons"]["L-1"]["status"] == "done"
    assert draft["steps"]["batch"]["status"] == "done"
    ids = [item["id"] for item in exercises(app)]
    assert ids == ["EX-1-1", "EX-1-2", "EX-1-3"]


def test_single_lesson_rewrite_uses_replace(tmp_path: Path) -> None:
    app = make_app(tmp_path, llm=FakeLlm(fixed_ids=True))
    seed_draft(app)
    store = app.app.state.studio_store
    assert app.post(
        "/api/studio/demo/lessons", json={"lesson_id": "L-1"}
    ).status_code == 200
    store.set_step("demo", "lessons", status="done", lesson_id="L-1")

    duplicate = app.post(
        "/api/studio/demo/lessons", json={"lesson_id": "L-1"}
    )

    assert duplicate.status_code == 200
    draft = store.load("demo")
    assert draft["steps"]["lessons"]["L-1"]["status"] == "failed"
    assert "已存在" in draft["steps"]["lessons"]["L-1"]["error"]

    rewritten = app.post("/api/studio/demo/lessons", json={
        "lesson_id": "L-1", "replace": True,
    })

    assert rewritten.status_code == 200
    draft = store.load("demo")
    assert draft["steps"]["lessons"]["L-1"]["status"] == "done"
    assert [item["id"] for item in exercises(app)] == [
        "EX-1-1", "EX-1-2", "EX-1-3",
    ]


def test_save_outline_rejected_while_batch_is_running(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed_draft(app)
    store = app.app.state.studio_store
    before = store.read("demo", "outline.html")
    store.set_step("demo", "batch", status="running", extra={
        "mode": "lessons", "done": 0, "total": 2,
    })

    response = app.put("/api/studio/demo/outline", json={"html": before})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "step_running"
    assert store.read("demo", "outline.html") == before

    store.set_step("demo", "batch", status="done")
    allowed = app.put("/api/studio/demo/outline", json={"html": before})
    assert allowed.status_code == 200, allowed.text


def test_batch_rejected_while_single_job_runs(tmp_path: Path) -> None:
    release = threading.Event()
    started = threading.Event()
    llm = FakeLlm(block=release, started=started)
    app = make_app(tmp_path, llm=llm, inline=False)
    seed_draft(app)
    store = app.app.state.studio_store

    assert app.post("/api/studio/demo/outline").status_code == 200
    assert started.wait(5), "outline job did not start"

    response = app.post("/api/studio/demo/batch", json={"mode": "research"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "step_running"
    release.set()
    assert wait_for(
        lambda: store.load("demo")["steps"]["outline"]["status"] == "done"
    )


def test_single_job_rejected_while_batch_runs(tmp_path: Path) -> None:
    release = threading.Event()
    started = threading.Event()
    search = FakeSearch(block=release, started=started)
    app = make_app(tmp_path, search=search, inline=False)
    seed_draft(app)
    store = app.app.state.studio_store

    batch = app.post("/api/studio/demo/batch", json={"mode": "research"})

    assert batch.status_code == 200, batch.text
    assert started.wait(5), "batch search did not start"
    response = app.post(
        "/api/studio/demo/lessons", json={"lesson_id": "L-1"}
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "step_running"
    release.set()
    assert wait_for(
        lambda: store.load("demo")["steps"]["batch"]["status"] == "done"
    )


def test_draft_page_shows_batch_and_rewrite_controls(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed_draft(app)
    store = app.app.state.studio_store
    store.set_step("demo", "lessons", status="done", lesson_id="L-1")
    store.set_step("demo", "batch", status="done", extra={
        "mode": "lessons", "done": 1, "total": 2,
    })

    page = app.get("/studio/demo").text

    assert "全部调研" in page
    assert "全部写课" in page
    assert 'data-batch-status="research"' in page
    assert 'data-batch-status="lessons"' in page
    assert 'data-action="rewrite"' in page
    assert "lessons · done · 完成 1/2" in page


def test_multi_module_batch_end_to_end(tmp_path: Path) -> None:
    llm = FakeLlm(outline=MULTI_OUTLINE_JSON)
    search = FakeSearch()
    app = make_app(tmp_path, llm=llm, search=search)
    store = app.app.state.studio_store

    created = app.post("/studio", data={
        "draft_id": "demo", "topic": "双模块课程", "level": "L2",
        "module_count": "2", "lessons_per_module": "2",
        "searches_per_lesson": "5",
    })

    assert created.status_code == 200, created.text
    draft = store.load("demo")
    assert draft["module_count"] == 2
    assert draft["lessons_per_module"] == 2
    assert draft["lesson_count"] == 4
    assert draft["steps"]["outline"]["status"] == "done"

    lesson_ids = ["L-1", "L-2", "L-3", "L-4"]
    research = app.post("/api/studio/demo/batch", json={"mode": "research"})

    assert research.status_code == 200, research.text
    assert research.json()["started"] == lesson_ids
    draft = store.load("demo")
    assert draft["steps"]["batch"]["status"] == "done"
    assert draft["steps"]["batch"]["mode"] == "research"
    assert draft["steps"]["batch"]["done"] == 4
    assert draft["steps"]["batch"]["total"] == 4
    for lesson_id in lesson_ids:
        assert draft["steps"]["research"][lesson_id]["status"] == "done"

    lessons = app.post("/api/studio/demo/batch", json={"mode": "lessons"})

    assert lessons.status_code == 200, lessons.text
    assert lessons.json()["started"] == lesson_ids
    draft = store.load("demo")
    assert draft["steps"]["batch"]["status"] == "done"
    assert draft["steps"]["batch"]["mode"] == "lessons"
    assert draft["steps"]["batch"]["done"] == 4
    assert draft["steps"]["batch"]["total"] == 4
    for lesson_id in lesson_ids:
        assert draft["steps"]["lessons"][lesson_id]["status"] == "done"
    assert llm.lesson_calls == 4

    validation = app.post(
        "/api/studio/demo/validate", json={"skip_verify": True}
    )

    assert validation.status_code == 200, validation.text
    assert validation.json()["ok"] is True, validation.json()["errors"]

    promoted = app.post(
        "/api/studio/demo/promote", json={"skip_verify": True}
    )

    assert promoted.status_code == 200, promoted.text
    target = tmp_path / "packs" / "demo"
    report = validate_pack(target)
    assert report.errors == []

    m01 = yaml.safe_load(store.read("demo", "modules/M01/module.yaml"))
    m02 = yaml.safe_load(store.read("demo", "modules/M02/module.yaml"))
    assert m01["id"] == "M01"
    assert m01["concepts"] == ["c-one"]
    assert m01["lessons"] == ["L-1", "L-2"]
    assert m01["order"] == 1
    assert m02["id"] == "M02"
    assert m02["concepts"] == ["c-one"]
    assert m02["lessons"] == ["L-3", "L-4"]
    assert m02["order"] == 2
    for module_id, lesson_id in (
        ("M01", "L-1"), ("M01", "L-2"),
        ("M02", "L-3"), ("M02", "L-4"),
    ):
        lesson_path = (
            target / "modules" / module_id / "lessons" / f"{lesson_id}.html"
        )
        assert lesson_path.is_file()
        assert f'"module": "{module_id}"' in lesson_path.read_text(
            encoding="utf-8"
        )

    assert len(exercises(app)) == 12

    again_research = app.post(
        "/api/studio/demo/batch", json={"mode": "research"}
    )
    again_lessons = app.post(
        "/api/studio/demo/batch", json={"mode": "lessons"}
    )

    assert again_research.json() == {"started": []}
    assert again_lessons.json() == {"started": []}
    assert llm.lesson_calls == 4

    rewritten = app.post(
        "/api/studio/demo/lessons",
        json={"lesson_id": "L-1", "replace": True},
    )

    assert rewritten.status_code == 200, rewritten.text
    after = exercises(app)
    assert len(after) == 12
    ids = [item["id"] for item in after]
    assert len(ids) == len(set(ids))
    assert "EX-1-1" not in ids
    assert "EX-5-1" in ids
    assert store.load("demo")["steps"]["lessons"]["L-1"]["status"] == "done"


def test_moved_done_lesson_is_rewritten_into_its_new_module(
    tmp_path: Path,
) -> None:
    llm = FakeLlm(outline=MULTI_OUTLINE_JSON)
    app = make_app(tmp_path, llm=llm)
    store = app.app.state.studio_store

    created = app.post("/studio", data={
        "draft_id": "demo", "topic": "双模块课程", "level": "L2",
        "module_count": "2", "lessons_per_module": "2",
        "searches_per_lesson": "5",
    })
    assert created.status_code == 200, created.text
    written = app.post("/api/studio/demo/lessons", json={"lesson_id": "L-3"})
    assert written.status_code == 200, written.text
    assert store.load("demo")["steps"]["lessons"]["L-3"]["status"] == "done"
    drafts = tmp_path / "drafts" / "demo"
    assert (drafts / "modules/M02/lessons/L-3.html").is_file()

    modules = parse_outline_html(store.read("demo", "outline.html"))
    m01, m02 = modules
    moved = next(item for item in m02.lessons if item.lesson_id == "L-3")
    m01 = ModulePlan(m01.module_id, m01.title, m01.concepts, [
        *m01.lessons, moved,
    ])
    m02 = ModulePlan(m02.module_id, m02.title, m02.concepts, [
        item for item in m02.lessons if item.lesson_id != "L-3"
    ])

    saved = app.put("/api/studio/demo/outline", json={
        "html": render_outline_html("双模块包", [m01, m02]),
    })

    assert saved.status_code == 200, saved.text
    entry = store.load("demo")["steps"]["lessons"]["L-3"]
    assert entry["status"] == "failed"
    assert entry["error"] == "课程已移动到新模块，需要重写"

    batch = app.post("/api/studio/demo/batch", json={"mode": "lessons"})

    assert batch.status_code == 200, batch.text
    assert "L-3" in batch.json()["started"]
    assert (drafts / "modules/M01/lessons/L-3.html").is_file()
    # The stale file in the old module is left in place, not deleted.
    assert (drafts / "modules/M02/lessons/L-3.html").is_file()
    assert store.load("demo")["steps"]["lessons"]["L-3"]["status"] == "done"
    assert validate_pack(drafts).errors == []
