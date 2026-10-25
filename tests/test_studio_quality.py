import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

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

LOW_LEVEL_JSON = (
    '{"manifest": {"title": "单线程执行器", "minutes": 20, '
    '"objectives": ["说明调度顺序"]}, '
    '"html": "<article class=\\"tb-lesson\\"><h1>课</h1>'
    '<div data-tb-exercise=\\"EX-1\\"></div>'
    '<div data-tb-exercise=\\"EX-2\\"></div></article>", '
    '"exercises": ['
    '{"id": "EX-1", "type": "single_choice", '
    '"concepts": ["executor-basics"], "level": "L1", "prompt": "选一个", '
    '"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}], '
    '"answer": "a"}, '
    '{"id": "EX-2", "type": "multi_choice", '
    '"concepts": ["executor-basics"], "level": "L1", "prompt": "多选", '
    '"options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}], '
    '"answer": ["a"]}], '
    '"resources": [{"id": "DOC-1", "title": "Executors", '
    '"url": "https://docs.ros.org/x", "type": "official-doc", '
    '"trust": "A", "license": "Apache-2.0", '
    '"last_verified": "2026-10-25", "coverage": ["executor-basics"], '
    '"why": "官方"}]}'
)


class FakeLlm:
    def __init__(self, lesson_json: str) -> None:
        self.lesson_json = lesson_json

    def complete(self, system: str, user: str) -> str:
        if "课程设计师" in system:
            return OUTLINE_JSON
        return self.lesson_json


class FakeSearch:
    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        return [SearchHit(
            title="Executors", url="https://docs.ros.org/x", snippet="",
            summary="", content="", authority=3,
        )]

    def fetch(self, url: str) -> str:
        return ""


SAMPLE = Path(__file__).parents[1] / "content-packs" / "ros2-qos"


def make_app(tmp_path: Path, lesson_json: str) -> TestClient:
    return TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts",
        studio_packs=tmp_path / "packs",
        studio_llm=FakeLlm(lesson_json),
        studio_search=FakeSearch(),
        studio_config=CONFIG,
    ))


def create_draft(app: TestClient, draft_id: str = "demo") -> None:
    response = app.post("/studio", data={
        "draft_id": draft_id, "topic": "ROS 2 执行器", "level": "L2",
        "lesson_count": "1", "searches_per_lesson": "5",
    }, follow_redirects=False)
    assert response.status_code == 303


def run_lessons(app: TestClient, draft_id: str = "demo") -> None:
    create_draft(app, draft_id)
    assert app.post(
        f"/api/studio/{draft_id}/research", json={"lesson_id": "L-EXEC-001"}
    ).status_code == 200
    assert app.post(
        f"/api/studio/{draft_id}/lessons", json={"lesson_id": "L-EXEC-001"}
    ).status_code == 200


def test_quality_gate_blocks_promote(tmp_path: Path) -> None:
    app = make_app(tmp_path, LOW_LEVEL_JSON)
    run_lessons(app)

    validation = app.post(
        "/api/studio/demo/validate", json={"skip_verify": True}
    )
    assert validation.status_code == 200
    payload = validation.json()
    assert payload["ok"] is False
    assert payload["quality"]["ok"] is False
    assert any("lesson_level_short" in item for item in payload["errors"])

    promote = app.post(
        "/api/studio/demo/promote", json={"skip_verify": True}
    )
    assert promote.status_code == 400
    assert promote.json()["detail"]["code"] == "quality_gate"


def test_force_does_not_bypass_quality(tmp_path: Path) -> None:
    app = make_app(tmp_path, LOW_LEVEL_JSON)
    run_lessons(app)
    (tmp_path / "packs" / "demo").mkdir(parents=True)

    promote = app.post(
        "/api/studio/demo/promote",
        json={"force": True, "skip_verify": True},
    )

    assert promote.status_code == 400
    assert promote.json()["detail"]["code"] == "quality_gate"


def test_draft_page_shows_quality_score(tmp_path: Path) -> None:
    app = make_app(tmp_path, LOW_LEVEL_JSON)
    run_lessons(app)
    app.post("/api/studio/demo/validate", json={"skip_verify": True})

    page = app.get("/studio/demo").text

    assert "质量分" in page
    assert "硬错误" in page


def test_revalidation_clears_stale_quality_report(tmp_path: Path) -> None:
    app = make_app(tmp_path, LOW_LEVEL_JSON)
    run_lessons(app)

    first = app.post("/api/studio/demo/validate", json={"skip_verify": True})
    assert first.status_code == 200
    old_score = f"{first.json()['quality']['score']}/100"
    assert old_score in app.get("/studio/demo").text

    pack_path = tmp_path / "drafts" / "demo" / "pack.yaml"
    pack_path.write_text("schema: [unclosed", encoding="utf-8")

    second = app.post("/api/studio/demo/validate", json={"skip_verify": True})
    payload = second.json()
    assert payload["quality"] is None
    assert payload["quality_skipped"] == "invalid_pack"

    stored = app.app.state.studio_store.load("demo")["steps"]["validation"]
    assert stored["quality"] is None

    page = app.get("/studio/demo").text
    assert old_score not in page
