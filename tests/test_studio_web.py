import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.contract.validator import validate_pack
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
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if "课程设计师" in system:
            return OUTLINE_JSON
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


def make_app(tmp_path: Path) -> TestClient:
    return TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts",
        studio_packs=tmp_path / "packs",
        studio_llm=FakeLlm(),
        studio_search=FakeSearch(),
        studio_config=CONFIG,
    ))


def create_draft(app: TestClient, draft_id: str = "demo") -> None:
    response = app.post("/studio", data={
        "draft_id": draft_id, "topic": "ROS 2 执行器", "level": "L2",
        "lesson_count": "1", "searches_per_lesson": "5",
    }, follow_redirects=False)
    assert response.status_code == 303


def test_studio_list_page_renders(tmp_path: Path) -> None:
    assert "新建草稿" in make_app(tmp_path).get("/studio").text


def test_create_draft_runs_outline(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    create_draft(app)
    draft = app.app.state.studio_store.load("demo")
    assert draft["steps"]["outline"]["status"] == "done"
    assert (tmp_path / "drafts" / "demo" / "outline.html").is_file()


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
