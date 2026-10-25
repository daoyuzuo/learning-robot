from pathlib import Path

from testbridge.interview.store import InterviewAnswer, InterviewStore


def make_store(tmp_path: Path) -> InterviewStore:
    return InterviewStore(tmp_path / "interview.db")


def test_create_and_get_session(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    session = store.create_session(
        learner_id="local", pack_id="p",
        question_ids=["q1", "q2"], concept_ids=["c1"],
    )
    loaded = store.get_session(session.id)
    assert loaded is not None
    assert loaded.question_ids == ["q1", "q2"]
    assert loaded.status == "running"
    assert loaded.current_index == 0


def test_list_sessions_newest_first_with_limit(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    first = store.create_session(
        learner_id="local", pack_id="p", question_ids=["q1"], concept_ids=["c1"],
    )
    second = store.create_session(
        learner_id="local", pack_id="p", question_ids=["q2"], concept_ids=["c2"],
    )
    sessions = store.list_sessions("local", limit=1)
    assert [item.id for item in sessions] == [second.id]
    assert first.id != second.id


def test_update_session(tmp_path: Path) -> None:
    from dataclasses import replace

    store = make_store(tmp_path)
    session = store.create_session(
        learner_id="local", pack_id="p", question_ids=["q1"], concept_ids=["c1"],
    )
    store.update_session(replace(session, status="completed", current_index=1))
    loaded = store.get_session(session.id)
    assert loaded is not None
    assert loaded.status == "completed"
    assert loaded.current_index == 1


def test_answer_upsert_and_list(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    session = store.create_session(
        learner_id="local", pack_id="p", question_ids=["q1"], concept_ids=["c1"],
    )
    answer = InterviewAnswer(
        session_id=session.id, question_id="q1", answer="first", status="answered",
    )
    store.save_answer(answer)
    store.save_answer(InterviewAnswer(
        session_id=session.id, question_id="q1", answer="second", status="graded",
        llm_scores=[{"dimension": "d", "score": 0.5}],
    ))
    loaded = store.get_answer(session.id, "q1")
    assert loaded is not None
    assert loaded.answer == "second"
    assert loaded.status == "graded"
    assert loaded.llm_scores[0]["score"] == 0.5
    assert set(store.list_answers(session.id)) == {"q1"}


def test_missing_rows_return_none(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert store.get_session("nope") is None
    assert store.get_answer("nope", "q1") is None
