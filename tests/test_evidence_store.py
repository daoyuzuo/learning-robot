import json
import sqlite3
from dataclasses import asdict, replace
from pathlib import Path

import pytest

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


def test_concept_filter_is_case_sensitive_and_literal(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "e.db")
    store.append(new_event(kind="exercise_attempt", concept_ids=["c-one"], outcome="correct"))
    assert len(store.list(concept_id="c-one")) == 1
    assert store.list(concept_id="C-ONE") == []
    assert store.list(concept_id="%") == []


def test_export_import_preserves_all_fields(tmp_path: Path) -> None:
    store_a = EvidenceStore(tmp_path / "a.db")
    event = replace(
        new_event(
            kind="exercise_attempt",
            concept_ids=["c-one", "c-two"],
            lesson_id="L-ONE",
            exercise_id="EX-ONE",
            outcome="partial",
            score=0.5,
            max_score=1.0,
            payload={"nested": {"items": [1, 2, {"x": "值"}]}, "note": "text"},
            source="cli",
            session_id="S-ONE",
            learner_id="learner-1",
        ),
        supersedes="old-id",
    )
    store_a.append(event)
    export_path = tmp_path / "e.jsonl"
    assert store_a.export_jsonl(export_path) == 1

    store_b = EvidenceStore(tmp_path / "b.db")
    assert store_b.import_jsonl(export_path) == 1
    assert asdict(store_b.list()[0]) == asdict(event)


def test_same_id_does_not_overwrite_body(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "e.db")
    event = replace(
        new_event(kind="exercise_attempt", concept_ids=["c-one"]),
        id="fixed",
        payload={"a": 1},
    )
    assert store.append(event) is None
    store.append(replace(event, payload={"a": 2}))

    rows = store.list()
    assert len(rows) == 1
    assert rows[0].payload == {"a": 1}
    assert store.count() == 1


def test_import_rejects_not_null_violation(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "e.db")
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "bad",
                "learner_id": "local",
                "kind": None,
                "concept_ids": [],
                "payload": {},
                "source": "web",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(sqlite3.IntegrityError):
        store.import_jsonl(path)
