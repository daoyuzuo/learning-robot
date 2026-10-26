import json
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.tutor.config import TutorConfig
from web.app import create_app

CONFIG = TutorConfig(
    base_url="https://api.example.com/v1", api_key="sk-test",
    model="chat", timeout=5.0,
)
SAMPLE = Path(__file__).parents[1] / "content-packs" / "ros2-qos"


class FakeLlm:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, system: str, user: str) -> str:
        self.prompts.append(user)
        if "课程设计师" in system:
            return json.dumps({
                "pack_title": "计划课", "concepts": [{
                    "id": "c-one", "title": "概念", "domain": "d",
                    "target_level": "L2",
                }],
                "modules": [{
                    "id": "M01", "title": "M", "concepts": ["c-one"],
                    "lessons": [{
                        "id": "L-1", "title": "课", "minutes": 30,
                        "concepts": ["c-one"], "objectives": ["o"],
                        "exercise_intents": ["i"], "research_queries": ["q"],
                    }],
                }],
            })
        return "{}"


def make_app(tmp_path: Path) -> TestClient:
    return TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts",
        studio_packs=tmp_path / "packs",
        studio_llm=FakeLlm(),
        studio_search=type("S", (), {
            "search": lambda self, q, count=10: [],
            "fetch": lambda self, url: "",
        })(),
        studio_config=CONFIG,
        studio_url_checker=lambda urls: {},
    ))


def test_create_with_auto_plan_computes_counts(tmp_path: Path) -> None:
    app = make_app(tmp_path)

    response = app.post("/studio", data={
        "draft_id": "auto", "topic": "ROS2", "level": "L2",
        "searches_per_lesson": "5", "search_backend": "auto",
        "auto_plan": "on", "weekly_hours": "2", "horizon_weeks": "2",
        "purpose": "systematic", "must_cover": "时间同步, 测试",
    }, follow_redirects=False)

    assert response.status_code == 303
    draft = app.app.state.studio_store.load("auto")
    assert draft["plan"]["computed"]["total_lessons"] == 5
    assert draft["module_count"] == 1
    assert draft["lessons_per_module"] == 5
    assert draft["lesson_count"] == 5
    assert draft["plan"]["inputs"]["must_cover"] == ["时间同步", "测试"]


def test_create_with_invalid_auto_plan_is_rejected(tmp_path: Path) -> None:
    app = make_app(tmp_path)

    response = app.post("/studio", data={
        "draft_id": "bad", "topic": "ROS2", "level": "L2",
        "searches_per_lesson": "5", "search_backend": "auto",
        "auto_plan": "on", "weekly_hours": "0", "horizon_weeks": "2",
    }, follow_redirects=False)

    assert response.status_code == 400
    assert app.app.state.studio_store.exists("bad") is False
