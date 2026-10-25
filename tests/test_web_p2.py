import warnings
from pathlib import Path

# Environment-level deprecation emitted by the installed FastAPI/Starlette pair.
warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.learning.store import ReviewState
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


def test_progress_reports_filtered_and_global_totals(tmp_path: Path) -> None:
    c = client(tmp_path)
    c.post("/api/evidence", json={
        "lesson_id": "L-SYNC-001", "exercise_id": "EX-SYNC-001", "response": "c",
    })
    c.post("/api/evidence", json={
        "lesson_id": "L-SYNC-002", "exercise_id": "EX-SYNC-005", "response": ["a", "c", "d"],
    })

    filtered = c.get("/progress?concept=clock-drift").text
    assert "已按概念筛选：clock-drift" in filtered
    assert "本概念 1 条 / 全局 2 条" in filtered
    assert "EX-SYNC-005" in filtered
    assert "EX-SYNC-001" not in filtered

    other = c.get("/progress?concept=sensor-time-sync").text
    assert "本概念 1 条 / 全局 2 条" in other
    assert "EX-SYNC-001" in other
    assert "EX-SYNC-005" not in other

    unfiltered = c.get("/progress").text
    assert "共 2 条证据（显示最近 2 条）" in unfiltered
    assert "已按概念筛选" not in unfiltered


def test_review_lists_due_cards(tmp_path: Path) -> None:
    app = create_app(SAMPLE, tmp_path / "test.db")
    app.state.learning.store.upsert_review(ReviewState(
        learner_id="local", exercise_id="EX-SYNC-001",
        concept_ids=["sensor-time-sync"], due="2020-01-01T00:00:00+00:00",
        stability=1.0, difficulty=5.0, reps=1, lapses=0, state="Review",
        last_review=None,
        card_json={
            "card_id": 1, "state": 2, "step": 0, "stability": 1.0,
            "difficulty": 5.0, "due": "2020-01-01T00:00:00+00:00",
            "last_review": None,
        },
    ))

    text = TestClient(app).get("/review").text

    assert "EX-SYNC-001" in text
    assert "2020-01-01" in text
    assert 'href="/lesson/L-SYNC-001"' in text


def test_concepts_page_renders_prerequisite_graph(tmp_path: Path) -> None:
    text = client(tmp_path).get("/concepts").text
    assert 'class="tb-graph"' in text
    assert 'data-concept="qos-testing"' in text or 'data-concept="sensor-time-sync"' in text


def test_concepts_link_to_evidence(tmp_path: Path) -> None:
    c = client(tmp_path)
    text = c.get("/concepts").text
    assert 'href="/progress?concept=sensor-time-sync"' in text
