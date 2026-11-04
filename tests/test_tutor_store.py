import sqlite3
from pathlib import Path

from testbridge.evidence.store import EvidenceStore
from testbridge.tutor.store import TutorStore


def test_append_and_history_round_trip(tmp_path: Path) -> None:
    store = TutorStore(tmp_path / "t.db")
    store.append(
        learner_id="local", lesson_id="L-1", anchor="", role="user", content="问"
    )
    store.append(
        learner_id="local", lesson_id="L-1", anchor="", role="assistant",
        content="答", basis="lesson", citations=["DOC-1"], model="demo",
    )

    messages = store.history("local", "L-1")

    assert [message.content for message in messages] == ["问", "答"]
    assert messages[1].basis == "lesson"
    assert messages[1].citations == ["DOC-1"]
    assert messages[1].model == "demo"


def test_history_is_scoped_by_lesson_and_learner(tmp_path: Path) -> None:
    store = TutorStore(tmp_path / "t.db")
    store.append(learner_id="local", lesson_id="L-1", anchor="", role="user", content="a")
    store.append(learner_id="local", lesson_id="L-2", anchor="", role="user", content="b")
    store.append(learner_id="other", lesson_id="L-1", anchor="", role="user", content="c")

    assert [m.content for m in store.history("local", "L-1")] == ["a"]


def test_history_keeps_latest_messages(tmp_path: Path) -> None:
    store = TutorStore(tmp_path / "t.db")
    for index in range(30):
        store.append(
            learner_id="local", lesson_id="L-1", anchor="",
            role="user", content=f"q{index}",
        )

    messages = store.history("local", "L-1", limit=5)

    assert [m.content for m in messages] == ["q25", "q26", "q27", "q28", "q29"]


def test_tutor_messages_are_not_evidence(tmp_path: Path) -> None:
    path = tmp_path / "shared.db"
    store = TutorStore(path)
    store.append(learner_id="local", lesson_id="L-1", anchor="", role="user", content="问")

    assert EvidenceStore(path).count() == 0


def test_selection_round_trips(tmp_path: Path) -> None:
    store = TutorStore(tmp_path / "t.db")
    store.append(
        learner_id="local", lesson_id="L-1", anchor="",
        role="user", content="为什么？", selection="策略决定资源投向",
    )
    assert store.history("local", "L-1")[-1].selection == "策略决定资源投向"


def test_selection_defaults_to_empty(tmp_path: Path) -> None:
    store = TutorStore(tmp_path / "t.db")
    store.append(learner_id="local", lesson_id="L-1", anchor="", role="user", content="问")
    assert store.history("local", "L-1")[-1].selection == ""


def test_existing_database_gains_the_column_without_data_loss(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE tutor_message (
             id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, lesson_id TEXT NOT NULL,
             anchor TEXT NOT NULL DEFAULT '', role TEXT NOT NULL, content TEXT NOT NULL,
             basis TEXT, citations_json TEXT NOT NULL DEFAULT '[]', model TEXT,
             created_at TEXT NOT NULL)"""
    )
    conn.execute(
        "INSERT INTO tutor_message VALUES "
        "('1','local','L-1','','user','旧消息',NULL,'[]',NULL,'2026-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    # Initialising an older database must add the column, not rebuild the table.
    store = TutorStore(path)
    messages = store.history("local", "L-1")
    assert [m.content for m in messages] == ["旧消息"]
    assert messages[0].selection == ""

    store.append(learner_id="local", lesson_id="L-1", anchor="", role="user",
                 content="新消息", selection="片段")
    assert store.history("local", "L-1")[-1].selection == "片段"
