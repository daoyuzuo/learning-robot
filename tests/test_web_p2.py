import warnings
from pathlib import Path

# Environment-level deprecation emitted by the installed FastAPI/Starlette pair.
warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from web.app import create_app

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"


def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(SAMPLE, tmp_path / "test.db"))


def test_p2_pages_render(tmp_path: Path) -> None:
    c = client(tmp_path)
    assert c.get("/today").status_code == 200
    assert c.get("/concepts").status_code == 200
    assert c.get("/review").status_code == 200
    assert "sensor-time-sync" in c.get("/concepts").text
    assert "Readiness" in c.get("/").text


def test_today_shows_weak_after_wrong_answer(tmp_path: Path) -> None:
    c = client(tmp_path)
    c.post("/api/evidence", json={
        "lesson_id": "L-SYNC-001", "exercise_id": "EX-SYNC-001", "response": "wrong",
    })
    response = c.get("/today")
    assert response.status_code == 200
    assert "掌握度偏低" in response.text


def test_progress_includes_readiness(tmp_path: Path) -> None:
    c = client(tmp_path)
    response = c.get("/progress")
    assert response.status_code == 200
    assert "Readiness" in response.text


def test_dashboard_links_p2_pages(tmp_path: Path) -> None:
    c = client(tmp_path)
    text = c.get("/").text
    assert 'href="/today"' in text
    assert 'href="/concepts"' in text
    assert 'href="/review"' in text


def test_progress_shows_mastery_summary(tmp_path: Path) -> None:
    c = client(tmp_path)
    response = c.get("/progress")
    assert response.status_code == 200
    assert "掌握度" in response.text
    assert "<th>概念</th>" in response.text
    assert "<th>等级</th>" in response.text
    assert "<th>目标</th>" in response.text


def test_progress_filters_by_concept(tmp_path: Path) -> None:
    c = client(tmp_path)
    response = c.get("/progress?concept=sensor-time-sync")
    assert response.status_code == 200
    assert "sensor-time-sync" in response.text


def test_concepts_link_to_evidence(tmp_path: Path) -> None:
    c = client(tmp_path)
    text = c.get("/concepts").text
    assert 'href="/progress?concept=sensor-time-sync"' in text
