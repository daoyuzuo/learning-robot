from pathlib import Path

from testbridge.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


def test_validate_ok(capsys) -> None:
    assert main(["validate", str(FIXTURE)]) == 0
    assert "0 error" in capsys.readouterr().out


def test_validate_missing(tmp_path: Path) -> None:
    assert main(["validate", str(tmp_path / "nope")]) == 1


def test_evidence_round_trip(tmp_path: Path, capsys) -> None:
    from testbridge.evidence.store import EvidenceStore, new_event

    db = tmp_path / "e.db"
    store = EvidenceStore(db)
    store.append(new_event(kind="exercise_attempt", concept_ids=["c-one"]))
    out = tmp_path / "e.jsonl"
    assert main(["evidence-export", str(db), str(out)]) == 0
    assert out.is_file()
    assert main(["evidence-import", str(db), str(out)]) == 0
