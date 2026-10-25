import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from web.app import create_app

ROOT = Path(__file__).parents[1]
SAMPLE = ROOT / "content-packs" / "sample-sensors"
BANKS = ROOT / "interview-banks"


def make_app(tmp_path: Path, llm=None, config=None) -> TestClient:
    return TestClient(create_app(
        SAMPLE, tmp_path / "i.db",
        interview_banks=BANKS,
        interview_llm=llm,
        interview_config=config,
    ))


def test_interview_page_lists_weak_concepts(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    response = c.get("/interview")
    assert response.status_code == 200
    assert "开始模拟" in response.text
    assert "timestamp-basics" in response.text or "时间戳基础" in response.text


def test_start_redirects_to_session(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    response = c.post("/interview", data={"question_count": "3"},
                      follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/interview/session/")


def test_nav_shows_interview(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    assert 'href="/interview"' in c.get("/").text
