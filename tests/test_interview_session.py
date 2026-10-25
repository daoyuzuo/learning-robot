from pathlib import Path

import pytest

from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore
from testbridge.interview.bank import load_bank, resolve_bank_path
from testbridge.interview.session import InterviewService, SessionError
from testbridge.interview.store import InterviewStore
from testbridge.learning.service import LearningService
from testbridge.learning.store import LearningStore

ROOT = Path(__file__).parents[1]
PACK = load_pack(ROOT / "content-packs" / "sample-sensors")
BANK = load_bank(
    resolve_bank_path(PACK.root, PACK.meta.id, ROOT / "interview-banks"),
    pack_id=PACK.meta.id,
    concept_ids=set(PACK.concepts),
)


def make_service(tmp_path: Path) -> InterviewService:
    db = tmp_path / "i.db"
    evidence = EvidenceStore(db)
    learning = LearningService(PACK, evidence, LearningStore(db))
    bank = load_bank(
        resolve_bank_path(PACK.root, PACK.meta.id, ROOT / "interview-banks"),
        pack_id=PACK.meta.id,
        concept_ids=set(PACK.concepts),
    )
    return InterviewService(
        PACK, bank, InterviewStore(db), evidence, learning,
    )


def test_start_creates_three_question_session(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    session = service.start(3)
    assert len(session.question_ids) == 3
    assert session.status == "running"
    assert service.get(session.id).id == session.id


def test_start_rejects_bad_count(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    with pytest.raises(SessionError, match="3 或 5"):
        service.start(4)


def test_save_and_reset_draft(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    session = service.start(3)
    question_id = session.question_ids[0]
    answer = service.save_draft(session.id, question_id, "我的回答")
    assert answer.answer == "我的回答"
    assert answer.status == "answered"
    assert service.answers(session.id)[question_id].answer == "我的回答"
    reset = service.reset_answer(session.id, question_id)
    assert reset.answer == ""
    assert service.answers(session.id)[question_id].answer == ""


def test_draft_too_long_is_rejected(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    session = service.start(3)
    with pytest.raises(SessionError, match="10000"):
        service.save_draft(session.id, session.question_ids[0], "x" * 10001)


def test_unknown_question_is_rejected(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    session = service.start(3)
    with pytest.raises(SessionError):
        service.save_draft(session.id, "q-nope", "x")


def test_reset_rejects_foreign_question(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    session = service.start(3)
    with pytest.raises(SessionError):
        service.reset_answer(session.id, "q-nope")
    assert service.answers(session.id) == {}
