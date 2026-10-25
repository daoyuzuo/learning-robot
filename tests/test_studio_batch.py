"""Sequential batch jobs and single-lesson rewrite."""

import json
import threading
import time
from pathlib import Path

import yaml

from fastapi.testclient import TestClient

from testbridge.studio.outline import parse_outline_json, write_outline
from testbridge.studio.search import SearchHit
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
    ) -> None:
        self.fixed_ids = fixed_ids
        self.fail_on_call = fail_on_call
        self.block = block
        self.started = started
        self.lesson_calls = 0

    def complete(self, system: str, user: str) -> str:
        if "课程设计师" in system:
            if self.started is not None:
                self.started.set()
            if self.block is not None:
                self.block.wait(5)
            return OUTLINE_JSON
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

    page = app.get("/studio/demo").text

    assert "全部调研" in page
    assert "全部写课" in page
    assert 'data-batch-status="research"' in page
    assert 'data-batch-status="lessons"' in page
    assert 'data-action="rewrite"' in page
