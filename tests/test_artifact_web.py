import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from web.app import create_app

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"


def make_app(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(SAMPLE, tmp_path / "e.db", artifacts_dir=tmp_path / "artifacts")
    )


def upload(app: TestClient, **overrides):
    data = {
        "lesson_id": "L-SYNC-003",
        "exercise_id": "EX-SYNC-004",
        "notes": "同步误差测试",
        "checked": '["可复现", "判定"]',
    }
    data.update(overrides)
    return app.post(
        "/api/artifact",
        data=data,
        files={"file": ("run.log", b"offset=2ms", "text/plain")},
    )


def test_upload_stores_file_and_records_evidence(tmp_path: Path) -> None:
    app = make_app(tmp_path)

    response = upload(app)

    assert response.status_code == 200
    payload = response.json()
    evidence_id = payload["evidence_id"]
    stored = tmp_path / "artifacts" / evidence_id / "run.log"
    assert stored.read_bytes() == b"offset=2ms"
    assert payload["artifact_path"].endswith(f"{evidence_id}/run.log")

    event = app.app.state.store.get(evidence_id)
    assert event is not None
    assert event.kind == "artifact"
    assert event.payload["response"]["notes"] == "同步误差测试"
    assert event.payload["response"]["checked"] == ["可复现", "判定"]
    assert event.payload["filename"] == "run.log"
    assert event.payload["size"] == 10


def test_unsupported_type_is_400(tmp_path: Path) -> None:
    response = make_app(tmp_path).post(
        "/api/artifact",
        data={"lesson_id": "L-SYNC-003", "exercise_id": "EX-SYNC-004"},
        files={"file": ("run.exe", b"x", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "artifact_type"


def test_oversized_file_is_400(tmp_path: Path) -> None:
    big = b"x" * (10 * 1024 * 1024 + 1)
    response = make_app(tmp_path).post(
        "/api/artifact",
        data={"lesson_id": "L-SYNC-003", "exercise_id": "EX-SYNC-004"},
        files={"file": ("run.log", big, "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "artifact_size"


def test_cross_lesson_exercise_is_400(tmp_path: Path) -> None:
    response = upload(make_app(tmp_path), lesson_id="L-SYNC-001")
    assert response.status_code == 400
    assert response.json()["detail"] == "exercise not in lesson"


def test_unknown_exercise_is_404(tmp_path: Path) -> None:
    response = upload(make_app(tmp_path), exercise_id="EX-NOPE")
    assert response.status_code == 404


def test_non_artifact_exercise_is_400(tmp_path: Path) -> None:
    response = upload(
        make_app(tmp_path), lesson_id="L-SYNC-001", exercise_id="EX-SYNC-001"
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "not_artifact"
