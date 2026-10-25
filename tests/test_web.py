import warnings
from pathlib import Path

# Environment-level deprecation emitted by the installed FastAPI/Starlette pair.
warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.evidence.store import EvidenceStore, new_event
from web.app import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"
SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"


def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(FIXTURE, tmp_path / "test.db"))


def test_dashboard(tmp_path: Path) -> None:
    response = client(tmp_path).get("/")
    assert response.status_code == 200
    assert "Demo Module" in response.text


def test_lesson_page(tmp_path: Path) -> None:
    response = client(tmp_path).get("/lesson/L-ONE")
    assert response.status_code == 200
    assert "Pick A." in response.text
    assert "tb-runtime.js" in response.text


def test_submit_evidence(tmp_path: Path) -> None:
    response = client(tmp_path).post(
        "/api/evidence",
        json={"lesson_id": "L-ONE", "exercise_id": "EX-ONE", "response": "a"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["grade"]["correct"] is True
    assert payload["evidence_id"]


def test_progress_page(tmp_path: Path) -> None:
    c = client(tmp_path)
    c.post("/api/evidence", json={"lesson_id": "L-ONE", "exercise_id": "EX-ONE", "response": "a"})
    response = c.get("/progress")
    assert response.status_code == 200
    assert "EX-ONE" in response.text


def test_progress_page_reports_total_beyond_page_size(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    store = EvidenceStore(db)
    for _ in range(205):
        store.append(
            new_event(
                kind="exercise_attempt",
                concept_ids=["c-one"],
                lesson_id="L-ONE",
                exercise_id="EX-ONE",
            )
        )

    response = TestClient(create_app(FIXTURE, db)).get("/progress")

    assert response.status_code == 200
    assert "共 205 条证据（显示最近 200 条）" in response.text


def test_security_headers(tmp_path: Path) -> None:
    response = client(tmp_path).get("/")
    assert response.headers["content-security-policy"] == (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'"
    )


def test_unknown_lesson_is_404(tmp_path: Path) -> None:
    assert client(tmp_path).get("/lesson/NOPE").status_code == 404


def test_runtime_script_is_served(tmp_path: Path) -> None:
    response = client(tmp_path).get("/static/tb-runtime.js")
    assert response.status_code == 200
    assert "/api/evidence" in response.text
    assert "tb-widget-template" in response.text
    assert "eval(" not in response.text
    assert "new Function" not in response.text


def test_lesson_page_does_not_embed_exercise_data(tmp_path: Path) -> None:
    c = TestClient(create_app(FIXTURE, tmp_path / "test.db"))
    response = c.get("/lesson/L-ONE")
    assert response.status_code == 200
    assert "tb-exercise-data" not in response.text
    assert '"answer":' not in response.text


def test_cross_lesson_exercise_is_rejected(tmp_path: Path) -> None:
    c = TestClient(create_app(SAMPLE, tmp_path / "test.db"))
    response = c.post(
        "/api/evidence",
        json={"lesson_id": "L-SYNC-001", "exercise_id": "EX-SYNC-005", "response": "a"},
    )
    assert response.status_code == 400
    assert "exercise not in lesson" in response.text


def test_unknown_exercise_is_404(tmp_path: Path) -> None:
    c = TestClient(create_app(SAMPLE, tmp_path / "test.db"))
    response = c.post(
        "/api/evidence",
        json={"lesson_id": "L-SYNC-001", "exercise_id": "EX-NOPE", "response": "a"},
    )
    assert response.status_code == 404
    assert "exercise not found" in response.text


def test_unknown_lesson_evidence_is_404(tmp_path: Path) -> None:
    c = TestClient(create_app(SAMPLE, tmp_path / "test.db"))
    response = c.post(
        "/api/evidence",
        json={"lesson_id": "L-NOPE", "exercise_id": "EX-SYNC-001", "response": "a"},
    )
    assert response.status_code == 404
    assert "lesson not found" in response.text


def test_self_assess_evidence_kind(tmp_path: Path) -> None:
    app = create_app(SAMPLE, tmp_path / "test.db")
    response = TestClient(app).post(
        "/api/evidence",
        json={
            "lesson_id": "L-SYNC-001",
            "exercise_id": "EX-SYNC-003",
            "response": {"checked": ["机制"]},
        },
    )
    assert response.status_code == 200
    events = app.state.store.list(limit=10)
    assert len(events) == 1
    assert events[0].kind == "self_assess"
    assert events[0].exercise_id == "EX-SYNC-003"


def test_artifact_evidence_kind(tmp_path: Path) -> None:
    app = create_app(SAMPLE, tmp_path / "test.db")
    response = TestClient(app).post(
        "/api/evidence",
        json={
            "lesson_id": "L-SYNC-003",
            "exercise_id": "EX-SYNC-004",
            "response": {"path": "run.log", "checked": ["可复现"]},
        },
    )
    assert response.status_code == 200
    events = app.state.store.list(limit=10)
    assert len(events) == 1
    assert events[0].kind == "artifact"
    assert events[0].exercise_id == "EX-SYNC-004"
