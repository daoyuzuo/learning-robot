"""Content evolution page, API and history page."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from testbridge.studio.evolution import save_snapshot, snapshot_lesson
from testbridge.studio.outline import (
    LessonPlan,
    parse_outline_json,
    write_outline,
)
from testbridge.studio.search import SearchHit
from testbridge.tutor.config import TutorConfig
from web.app import create_app

CONFIG = TutorConfig(
    base_url="https://api.example.com/v1", api_key="sk-test",
    model="deepseek-chat", timeout=5.0,
)

OUTLINE_JSON = json.dumps({
    "pack_title": "演进包",
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
    def __init__(self) -> None:
        self.calls = 0
        self.fail_on_call: int | None = None

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if self.fail_on_call == self.calls:
            raise RuntimeError("model down")
        return lesson_json(self.calls)


class FakeSearch:
    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        return [SearchHit(
            title="文档", url="https://docs.example/x", snippet="",
            summary="", content="", authority=3,
        )]

    def fetch(self, url: str) -> str:
        return ""


SAMPLE = Path(__file__).parents[1] / "content-packs" / "ros2-qos"


def make_app(
    tmp_path: Path, llm: FakeLlm | None = None
) -> TestClient:
    return TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts",
        studio_packs=tmp_path / "packs",
        studio_llm=llm or FakeLlm(),
        studio_search=FakeSearch(),
        studio_config=CONFIG,
        studio_url_checker=lambda urls: {},
    ))


def seed_draft(app: TestClient, draft_id: str) -> None:
    store = app.app.state.studio_store
    store.create(
        draft_id=draft_id, topic="t", level="L2",
        module_count=1, lessons_per_module=2,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    write_outline(
        store, draft_id, parse_outline_json(OUTLINE_JSON, 1, 2)
    )


def write_lessons(app: TestClient, draft_id: str) -> None:
    store = app.app.state.studio_store
    for lesson_id in ("L-1", "L-2"):
        response = app.post(
            f"/api/studio/{draft_id}/lessons", json={"lesson_id": lesson_id}
        )
        assert response.status_code == 200, response.text
        # Simulate a draft written under the previous prompt version.
        store.set_step(
            draft_id, "lessons", status="done", lesson_id=lesson_id,
            extra={"prompt_version": "studio/1"},
        )


def seed_all(tmp_path: Path, llm: FakeLlm | None = None) -> TestClient:
    app = make_app(tmp_path, llm)
    for draft_id in ("demo", "other"):
        seed_draft(app, draft_id)
        write_lessons(app, draft_id)
    return app


def wait_until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_evolution_page_lists_drafts_and_lessons(tmp_path: Path) -> None:
    app = seed_all(tmp_path)

    page = app.get("/studio/evolution")

    assert page.status_code == 200
    text = page.text
    assert "内容演进" in text
    assert "开始重生成" in text
    assert "demo" in text
    assert "other" in text
    assert 'data-target="demo:L-1"' in text
    assert 'data-target="other:L-2"' in text
    assert "studio/1" in text


def test_evolution_api_rewrites_targets_across_drafts(tmp_path: Path) -> None:
    app = seed_all(tmp_path)

    response = app.post("/api/studio/evolution", json={"targets": [
        {"draft_id": "demo", "lesson_id": "L-1"},
        {"draft_id": "other", "lesson_id": "L-2"},
    ]})

    assert response.status_code == 200, response.text
    assert response.json()["started"] == 2

    state = app.get("/api/studio/evolution/status").json()
    assert state["status"] == "done"
    assert state["total"] == 2
    assert state["done"] == 2
    assert [item["draft_id"] for item in state["results"]] == [
        "demo", "other",
    ]
    for draft in state["results"]:
        assert draft["error"] is None
        assert draft["quality_before"] is not None
        assert draft["quality_after"] is not None
        assert draft["quality_before"]["possible"] > 0
        lesson = draft["lessons"][0]
        assert lesson["ok"] is True
        assert lesson["changed"]["html"] is True
        assert lesson["snapshot_before"].startswith("history/")
        assert lesson["snapshot_after"].startswith("history/")


def test_evolution_writes_snapshots_and_report(tmp_path: Path) -> None:
    app = seed_all(tmp_path)

    app.post("/api/studio/evolution", json={"targets": [
        {"draft_id": "demo", "lesson_id": "L-1"},
    ]})

    history = tmp_path / "drafts" / "demo" / "history" / "L-1"
    snapshots = sorted(history.glob("*.json"))
    assert len(snapshots) == 2
    reports = sorted(
        (tmp_path / "drafts" / "demo" / "history").glob("evolution-*.json")
    )
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["draft_id"] == "demo"
    assert report["lessons"][0]["lesson_id"] == "L-1"
    assert report["lessons"][0]["changed"]["html"] is True


def test_evolution_records_prompt_version_and_batch_step(
    tmp_path: Path,
) -> None:
    app = seed_all(tmp_path)

    app.post("/api/studio/evolution", json={"targets": [
        {"draft_id": "demo", "lesson_id": "L-1"},
    ]})

    draft = app.app.state.studio_store.load("demo")
    entry = draft["steps"]["lessons"]["L-1"]
    assert entry["status"] == "done"
    assert entry["prompt_version"] == "studio/5"
    assert entry["written_at"]
    batch = draft["steps"]["batch"]
    assert batch["status"] == "done"
    assert batch["mode"] == "evolve"
    assert batch["done"] == 1
    assert batch["total"] == 1


def test_history_page_shows_snapshot_and_current(tmp_path: Path) -> None:
    app = seed_all(tmp_path)
    app.post("/api/studio/evolution", json={"targets": [
        {"draft_id": "demo", "lesson_id": "L-1"},
    ]})

    page = app.get("/studio/demo/history/L-1")

    assert page.status_code == 200
    text = page.text
    assert "上一版快照" in text
    assert "当前内容" in text
    assert "studio/1" in text
    assert "studio/5" in text
    assert "练习题干" in text
    assert "EX-1-1" in text
    assert "EX-5-1" in text
    assert "文档" in text
    assert "https://docs.example/x" in text
    assert "资源可信 A 1" in text
    assert "data-action=\"restore\"" not in text


def test_history_page_without_snapshot_renders_empty_state(
    tmp_path: Path,
) -> None:
    app = make_app(tmp_path)
    seed_draft(app, "demo")

    page = app.get("/studio/demo/history/L-1")

    assert page.status_code == 200
    assert "暂无快照" in page.text


def test_history_page_labels_identical_snapshot(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed_draft(app, "demo")
    write_lessons(app, "demo")
    store = app.app.state.studio_store
    plan = LessonPlan(
        "L-1", "课一", 20, ["目标一"], [],
        module_id="M01", concepts=["c-one"],
    )
    save_snapshot(store, snapshot_lesson(store, "demo", plan))

    page = app.get("/studio/demo/history/L-1")

    assert page.status_code == 200
    text = page.text
    assert "当前内容与最近快照一致" in text
    assert "上一版快照" not in text
    # The identical snapshot stays visible instead of being hidden.
    assert "练习题干" in text
    assert "EX-1-1" in text


def test_evolution_script_labels_quality_once() -> None:
    script = (
        Path(__file__).parents[1] / "web" / "static" / "evolution.js"
    ).read_text(encoding="utf-8")

    assert "质量 质量" not in script
    assert script.count('"质量 ') == 1


def test_evolution_api_missing_targets_returns_400(tmp_path: Path) -> None:
    app = make_app(tmp_path)

    response = app.post("/api/studio/evolution", json={})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_request"


@pytest.mark.parametrize(
    ("targets", "code"),
    [
        ([], "invalid_request"),
        ([{"draft_id": "demo", "lesson_id": "L-404"}], "invalid_target"),
        ([{"draft_id": "missing", "lesson_id": "L-1"}], "invalid_target"),
        ([{"draft_id": "../evil", "lesson_id": "L-1"}], "invalid_target"),
        ([{"draft_id": "demo", "lesson_id": "../evil"}], "invalid_target"),
    ],
)
def test_evolution_rejects_invalid_targets(
    tmp_path: Path, targets: list[dict], code: str
) -> None:
    app = make_app(tmp_path)
    seed_draft(app, "demo")

    response = app.post(
        "/api/studio/evolution", json={"targets": targets}
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == code


def test_evolution_returns_conflict_while_running(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed_draft(app, "demo")
    entered = threading.Event()
    released = threading.Event()

    def process(draft_id: str, lesson_ids: list[str]) -> dict:
        entered.set()
        released.wait(timeout=5)
        return {
            "draft_id": draft_id, "error": None,
            "lessons": [
                {"lesson_id": item, "ok": True} for item in lesson_ids
            ],
        }

    app.app.state.evolution.start([("demo", ["L-1"])], process)
    assert entered.wait(timeout=5)
    try:
        response = app.post("/api/studio/evolution", json={"targets": [
            {"draft_id": "demo", "lesson_id": "L-2"},
        ]})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "evolution_running"
    finally:
        released.set()
    assert wait_until(
        lambda: app.app.state.evolution.status()["status"] != "running"
    )


def test_evolution_continues_after_one_lesson_fails(tmp_path: Path) -> None:
    llm = FakeLlm()
    app = seed_all(tmp_path, llm)
    llm.fail_on_call = llm.calls + 1

    response = app.post("/api/studio/evolution", json={"targets": [
        {"draft_id": "demo", "lesson_id": "L-1"},
        {"draft_id": "other", "lesson_id": "L-1"},
    ]})

    assert response.status_code == 200, response.text
    state = app.get("/api/studio/evolution/status").json()
    assert state["status"] == "failed"
    demo, other = state["results"]
    assert demo["lessons"][0]["ok"] is False
    assert "model down" in demo["lessons"][0]["error"]
    assert other["lessons"][0]["ok"] is True

    store = app.app.state.studio_store
    failed_batch = store.load("demo")["steps"]["batch"]
    assert failed_batch["status"] == "failed"
    assert failed_batch["error"] == "1 课失败"
    assert store.load("other")["steps"]["batch"]["status"] == "done"
    # The failed lesson keeps its before snapshot and is not rewritten.
    demo_snapshots = list(
        (tmp_path / "drafts" / "demo" / "history" / "L-1").glob("*.json")
    )
    assert len(demo_snapshots) == 1


def test_evolution_does_not_rewrite_when_before_snapshot_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm = FakeLlm()
    app = make_app(tmp_path, llm)
    seed_draft(app, "demo")
    write_lessons(app, "demo")
    lesson_path = (
        tmp_path / "drafts" / "demo"
        / "modules" / "M01" / "lessons" / "L-1.html"
    )
    original = lesson_path.read_text(encoding="utf-8")
    saves = {"count": 0}

    def failing_save(store, snapshot):
        saves["count"] += 1
        raise OSError("disk full")

    monkeypatch.setattr("web.studio.save_snapshot", failing_save)
    llm_calls_before = llm.calls

    response = app.post("/api/studio/evolution", json={"targets": [
        {"draft_id": "demo", "lesson_id": "L-1"},
    ]})

    assert response.status_code == 200, response.text
    assert saves["count"] == 1
    assert llm.calls == llm_calls_before
    assert lesson_path.read_text(encoding="utf-8") == original

    state = app.get("/api/studio/evolution/status").json()
    assert state["status"] == "failed"
    lesson = state["results"][0]["lessons"][0]
    assert lesson["ok"] is False
    assert "disk full" in lesson["error"]

    draft = app.app.state.studio_store.load("demo")
    assert draft["steps"]["lessons"]["L-1"]["status"] == "failed"
    assert draft["steps"]["lessons"]["L-1"]["error"] == "disk full"
    assert draft["steps"]["batch"]["status"] == "failed"


def test_evolution_page_disabled_shows_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("web.app.load_config", lambda: None)
    app = TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts",
        studio_packs=tmp_path / "packs",
    ))
    seed_draft(app, "demo")

    page = app.get("/studio/evolution")

    assert page.status_code == 200
    assert "未配置模型服务" in page.text
    assert 'data-enabled="false"' in page.text
    assert 'data-action="start" disabled' in page.text


def test_evolution_api_disabled_returns_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("web.app.load_config", lambda: None)
    app = TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts",
        studio_packs=tmp_path / "packs",
    ))
    seed_draft(app, "demo")

    response = app.post("/api/studio/evolution", json={"targets": [
        {"draft_id": "demo", "lesson_id": "L-1"},
    ]})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "tutor_disabled"
