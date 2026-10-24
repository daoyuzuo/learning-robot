from pathlib import Path

from testbridge.evidence.store import EvidenceStore, new_event


def test_append_and_list(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "e.db")
    event = new_event(
        kind="exercise_attempt", lesson_id="L-ONE", exercise_id="EX-ONE",
        concept_ids=["c-one"], outcome="correct", score=1.0, max_score=1.0,
    )
    store.append(event)
    rows = store.list(lesson_id="L-ONE")
    assert len(rows) == 1
    assert rows[0].exercise_id == "EX-ONE"
    assert store.count(lesson_id="L-ONE") == 1


def test_export_import_is_idempotent(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "e.db")
    event = new_event(kind="exercise_attempt", concept_ids=["c-one"], outcome="correct")
    store.append(event)
    export_path = tmp_path / "e.jsonl"
    assert store.export_jsonl(export_path) == 1
    assert store.import_jsonl(export_path) == 0
    assert store.count() == 1


def test_concept_filter(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "e.db")
    store.append(new_event(kind="exercise_attempt", concept_ids=["c-one"], outcome="correct"))
    store.append(new_event(kind="exercise_attempt", concept_ids=["c-two"], outcome="incorrect"))
    assert len(store.list(concept_id="c-one")) == 1
