import html
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.studio.search import SearchHit
from testbridge.studio.search_router import SearchRoute
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


class FakeLlm:
    def complete(self, system: str, user: str) -> str:
        return OUTLINE_JSON


class FakeSearch:
    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        return [SearchHit(
            title="Executors", url="https://docs.ros.org/x", snippet="",
            summary="", content="", authority=3,
        )]

    def fetch(self, url: str) -> str:
        return ""


class RecordingRouter:
    def __init__(self, route_name: str = "openalex") -> None:
        self.route_name = route_name
        self.calls: list[dict] = []

    def route(self, backend, *, topic, concept_titles, concept_domains):
        self.calls.append({
            "backend": backend, "topic": topic,
            "titles": list(concept_titles), "domains": list(concept_domains),
        })
        return SearchRoute(self.route_name, FakeSearch())


SAMPLE = Path(__file__).parents[1] / "content-packs" / "ros2-qos"


def make_app(tmp_path: Path, router: RecordingRouter) -> TestClient:
    return TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts",
        studio_packs=tmp_path / "packs",
        studio_llm=FakeLlm(),
        studio_search=router,
        studio_config=CONFIG,
    ))


def create_draft(
    app: TestClient, draft_id: str = "demo", backend: str = "openalex"
) -> None:
    response = app.post("/studio", data={
        "draft_id": draft_id, "topic": "ROS 2 执行器", "level": "L2",
        "lesson_count": "1", "searches_per_lesson": "5",
        "search_backend": backend,
    }, follow_redirects=False)
    assert response.status_code == 303


def test_draft_persists_search_backend(tmp_path: Path) -> None:
    app = make_app(tmp_path, RecordingRouter())
    create_draft(app)

    draft = app.app.state.studio_store.load("demo")
    assert draft["search_backend"] == "openalex"
    assert "检索源 openalex" in app.get("/studio/demo").text


def test_research_uses_selected_backend_and_records_it(tmp_path: Path) -> None:
    router = RecordingRouter()
    app = make_app(tmp_path, router)
    create_draft(app)

    response = app.post(
        "/api/studio/demo/research", json={"lesson_id": "L-EXEC-001"}
    )

    assert response.status_code == 200
    assert router.calls[0]["backend"] == "openalex"
    assert router.calls[0]["titles"] == ["执行器基础"]
    assert router.calls[0]["domains"] == ["ros2"]

    draft = app.app.state.studio_store.load("demo")
    assert draft["steps"]["research"]["L-EXEC-001"]["backend"] == "openalex"
    dossier = app.app.state.studio_store.read(
        "demo", "research/L-EXEC-001.json"
    )
    assert '"backend": "openalex"' in dossier


def test_invalid_search_backend_is_rejected(tmp_path: Path) -> None:
    app = make_app(tmp_path, RecordingRouter())
    response = app.post("/studio", data={
        "draft_id": "demo", "topic": "t", "level": "L2",
        "lesson_count": "1", "searches_per_lesson": "5",
        "search_backend": "bogus",
    }, follow_redirects=False)

    assert response.status_code == 400


def test_old_draft_without_backend_routes_auto(tmp_path: Path) -> None:
    router = RecordingRouter()
    app = make_app(tmp_path, router)
    create_draft(app)

    store = app.app.state.studio_store
    draft = store.load("demo")
    del draft["search_backend"]
    store.save(draft)

    response = app.post(
        "/api/studio/demo/research", json={"lesson_id": "L-EXEC-001"}
    )

    assert response.status_code == 200
    assert router.calls[0]["backend"] == "auto"


def test_research_row_shows_route_name(tmp_path: Path) -> None:
    router = RecordingRouter(route_name="auto:openalex->deepseek")
    app = make_app(tmp_path, router)
    create_draft(app, backend="auto")

    response = app.post(
        "/api/studio/demo/research", json={"lesson_id": "L-EXEC-001"}
    )
    assert response.status_code == 200

    page = html.unescape(app.get("/studio/demo").text)
    assert "auto:openalex->deepseek" in page
