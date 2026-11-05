"""The Web app mirrors answers into the snapshot and reads it back on startup."""

import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.evidence.store import EvidenceStore
from testbridge.sync import EVIDENCE_FILE
from web.app import create_app

SAMPLE = Path(__file__).parents[1] / "tests" / "fixtures" / "packs" / "sample-sensors"


def submit(client: TestClient, response: str = "c") -> str:
    reply = client.post(
        "/api/evidence",
        json={
            "lesson_id": "L-SYNC-001",
            "exercise_id": "EX-SYNC-001",
            "response": response,
        },
    )
    assert reply.status_code == 200
    return reply.json()["evidence_id"]


def test_submitting_an_answer_writes_the_snapshot(tmp_path: Path) -> None:
    db = tmp_path / "web.db"
    state_dir = tmp_path / "state"
    client = TestClient(create_app(SAMPLE, db, state_dir=state_dir))

    evidence_id = submit(client)

    lines = (state_dir / EVIDENCE_FILE).read_text(encoding="utf-8").splitlines()
    assert any(evidence_id in line for line in lines)
    report = client.get("/progress")
    assert report.status_code == 200
    assert state_dir.as_posix() in report.text


def test_a_fresh_database_restores_from_the_snapshot(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    first = TestClient(create_app(SAMPLE, tmp_path / "first.db", state_dir=state_dir))
    evidence_id = submit(first)

    # Second session, brand new database, same snapshot directory.
    second_db = tmp_path / "second.db"
    second = TestClient(create_app(SAMPLE, second_db, state_dir=state_dir))
    assert EvidenceStore(second_db).count() == 1
    assert EvidenceStore(second_db).get(evidence_id) is not None

    # The restored answer is visible through the page, and derived state was
    # replayed from it rather than copied out of the snapshot.
    text = second.get("/progress?concept=sensor-time-sync").text
    assert "\u672c\u6982\u5ff5 1 \u6761" in text
    assert "L4" in second.get("/concepts").text


def test_default_state_dir_sits_next_to_the_database(tmp_path: Path) -> None:
    db = tmp_path / "web.db"
    client = TestClient(create_app(SAMPLE, db))
    submit(client)
    assert (tmp_path / "state" / EVIDENCE_FILE).is_file()
    # Nothing was written into the repository's own snapshot when tests run.
    assert client.app.state.state_dir == tmp_path / "state"


def test_sync_disabled_keeps_answers_in_the_database_only(tmp_path: Path) -> None:
    db = tmp_path / "web.db"
    client = TestClient(create_app(SAMPLE, db, state_dir="0"))
    evidence_id = submit(client)
    assert EvidenceStore(db).get(evidence_id) is not None
    assert not (tmp_path / "state").exists()


def test_unwritable_snapshot_does_not_block_submission(tmp_path: Path) -> None:
    db = tmp_path / "web.db"
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    client = TestClient(create_app(SAMPLE, db, state_dir=blocked / "state"))

    evidence_id = submit(client)

    assert EvidenceStore(db).get(evidence_id) is not None
    assert "快照写入失败" in client.app.state.sync_status["error"]
    text = client.get("/progress").text
    assert "快照写入失败" in text
    assert "答题仍保存在本地数据库" in text