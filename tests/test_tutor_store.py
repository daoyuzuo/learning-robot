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
