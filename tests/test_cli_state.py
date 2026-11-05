"""`tb state-*` commands: snapshot, merge, and rebuild in one step."""

import json
from pathlib import Path

from testbridge.cli import main
from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.learning.service import LearningService
from testbridge.learning.store import LearningStore

SAMPLE = Path(__file__).parents[1] / "tests" / "fixtures" / "packs" / "sample-sensors"


def test_state_export_writes_snapshot(tmp_path: Path, capsys) -> None:
    db = tmp_path / "e.db"
    EvidenceStore(db).append(
        new_event(kind="exercise_attempt", concept_ids=["c-one"], lesson_id="L-ONE")
    )
    target = tmp_path / "state"
    assert main(
        ["state-export", "--db", str(db), "--dir", str(target)]
    ) == 0
    out = capsys.readouterr().out
    assert "events: 1" in out
    assert "changed: yes" in out
    assert (target / "evidence.jsonl").is_file()


def test_state_import_merges_into_an_empty_database(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source.db"
    EvidenceStore(source).append(
        new_event(kind="exercise_attempt", concept_ids=["c-one"], lesson_id="L-ONE")
    )
    target = tmp_path / "state"
    main(["state-export", "--db", str(source), "--dir", str(target)])
    capsys.readouterr()

    fresh = tmp_path / "fresh.db"
    assert main(["state-import", "--db", str(fresh), "--dir", str(target)]) == 0
    out = capsys.readouterr().out
    assert "imported 1" in out
    assert EvidenceStore(fresh).count() == 1


def test_state_sync_with_pack_rebuilds_mastery(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source.db"
    service = LearningService(
        load_pack(SAMPLE), EvidenceStore(source), LearningStore(source)
    )
    service.evidence.append(
        new_event(
            kind="exercise_attempt",
            concept_ids=["sensor-time-sync"],
            lesson_id="L-SYNC-002",
            exercise_id="EX-SYNC-001",
            outcome="correct",
            score=1.0,
            max_score=1.0,
        )
    )
    target = tmp_path / "state"
    main(["state-export", "--db", str(source), "--dir", str(target)])
    capsys.readouterr()

    fresh = tmp_path / "fresh.db"
    assert main(
        [
            "state-sync", "--db", str(fresh), "--dir", str(target),
            "--pack", str(SAMPLE),
        ]
    ) == 0
    out = capsys.readouterr().out
    assert "imported 1" in out
    restored = LearningService(
        load_pack(SAMPLE), EvidenceStore(fresh), LearningStore(fresh)
    )
    assert restored.store.get_mastery("local", "sensor-time-sync") is not None
    assert restored.store.get_review("local", "EX-SYNC-001") is not None


def test_state_export_rejects_disabled_directory(tmp_path: Path, capsys) -> None:
    code = main(
        ["state-export", "--db", str(tmp_path / "e.db"), "--dir", "0"]
    )
    assert code == 2
    assert "ERROR state:" in capsys.readouterr().err


def test_state_import_reports_dirty_lines_as_warnings(tmp_path: Path, capsys) -> None:
    target = tmp_path / "state"
    target.mkdir()
    (target / "evidence.jsonl").write_text(
        json.dumps({"id": "x"}) + "\n", encoding="utf-8"
    )
    assert main(
        ["state-import", "--db", str(tmp_path / "e.db"), "--dir", str(target)]
    ) == 0
    captured = capsys.readouterr()
    assert "WARN evidence.jsonl line 1" in captured.err
    assert "Traceback" not in captured.err
