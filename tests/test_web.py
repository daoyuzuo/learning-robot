import shutil
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


def test_exercise_data_escapes_script_close(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(FIXTURE, pack)
    exercises_file = pack / "exercises.yaml"
    content = exercises_file.read_text(encoding="utf-8")
    exercises_file.write_text(
        content.replace(
            "prompt: Pick A.",
            "prompt: 'Pick A. </script><script>alert(1)</script>'",
        ),
        encoding="utf-8",
    )

    response = TestClient(create_app(pack, tmp_path / "test.db")).get("/lesson/L-ONE")

    assert response.status_code == 200
    body = response.text
    assert "</script><script>alert(1)" not in body
    assert "\\u003c/script\\u003e" in body
    # Only the two template-owned closing tags remain.
    assert body.count("</script>") == 2


def test_runtime_script_is_served(tmp_path: Path) -> None:
    response = client(tmp_path).get("/static/tb-runtime.js")
    assert response.status_code == 200
    assert "/api/evidence" in response.text
    assert "tb-widget-template" in response.text
    assert "JSON.parse" in response.text
    assert "eval(" not in response.text
    assert "new Function" not in response.text
