import json
import re
from pathlib import Path

import pytest

from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore
from testbridge.interview.bank import load_bank, resolve_bank_path
from testbridge.interview.session import InterviewService, SessionError
from testbridge.interview.store import InterviewStore
from testbridge.learning.service import LearningService
from testbridge.learning.store import LearningStore
from testbridge.tutor.config import TutorConfig

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


CONFIG = TutorConfig(base_url="http://x", api_key="k", model="fake")


class FakeClient:
    """Reply with one valid dimension per rubric line in the prompt."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        dimensions = re.findall(r"^- (.+?)（权重", user, flags=re.MULTILINE)
        return json.dumps({
            "scores": [
                {"dimension": dimension, "score": 0.6, "rationale": "ok"}
                for dimension in dimensions
            ],
            "summary": "继续", "strengths": [], "gaps": [],
        }, ensure_ascii=False)


def confirm_scores(suggestion, score: float) -> list[dict]:
    return [
        {"dimension": item.dimension, "score": score}
        for item in suggestion.scores
    ]


def test_grade_and_confirm_writes_evidence(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.llm = FakeClient()
    service.config = CONFIG
    session = service.start(3)
    question_id = session.question_ids[0]
    service.save_draft(session.id, question_id, "我的回答")
    suggestion = service.grade(session.id, question_id)
    assert suggestion.mode == "llm"
    evidence_id = service.confirm(
        session.id, question_id, confirm_scores(suggestion, 0.6),
        duration_ms=1000,
    )
    event = service.evidence_store.get(evidence_id)
    assert event is not None
    assert event.kind == "interview"
    assert event.session_id == session.id
    assert event.score == 0.6
    assert event.payload["question_id"] == question_id
    assert event.payload["reviewed_by_user"] is True


def test_confirm_is_idempotent(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.llm = FakeClient()
    service.config = CONFIG
    session = service.start(3)
    question_id = session.question_ids[0]
    service.save_draft(session.id, question_id, "答案")
    suggestion = service.grade(session.id, question_id)
    scores = confirm_scores(suggestion, 0.6)
    first = service.confirm(session.id, question_id, scores)
    second = service.confirm(session.id, question_id, [])
    assert first == second
    assert service.evidence_store.count() == 1


def test_confirm_requires_grading(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    session = service.start(3)
    question_id = session.question_ids[0]
    service.save_draft(session.id, question_id, "答案")
    with pytest.raises(SessionError, match="评分"):
        service.confirm(session.id, question_id, [])


def test_grade_requires_answer(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    session = service.start(3)
    with pytest.raises(SessionError, match="作答"):
        service.grade(session.id, session.question_ids[0])


def test_confirm_advances_and_completes(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.llm = FakeClient()
    service.config = CONFIG
    session = service.start(3)
    for index, question_id in enumerate(session.question_ids):
        service.save_draft(session.id, question_id, "答案")
        suggestion = service.grade(session.id, question_id)
        service.confirm(
            session.id, question_id, confirm_scores(suggestion, 0.6)
        )
        current = service.get(session.id)
        if index < 2:
            assert current.current_index == index + 1
            assert current.status == "running"
    assert service.get(session.id).status == "completed"


def test_abandon_blocks_further_actions(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    session = service.start(3)
    service.abandon(session.id)
    assert service.get(session.id).status == "abandoned"
    with pytest.raises(SessionError, match="结束"):
        service.save_draft(session.id, session.question_ids[0], "x")


def test_summary_uses_confirmed_answers(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.llm = FakeClient()
    service.config = CONFIG
    session = service.start(3)
    question_id = session.question_ids[0]
    service.save_draft(session.id, question_id, "答案")
    suggestion = service.grade(session.id, question_id)
    service.confirm(session.id, question_id, confirm_scores(suggestion, 0.2))
    summary = service.summary(session.id)
    assert summary.total == 0.2
    assert set(summary.dimension_averages) == {
        item.dimension for item in suggestion.scores
    }
    assert set(summary.dimension_averages.values()) == {0.2}
    assert summary.weakest_concepts == list(
        service.bank.by_id(question_id).concepts
    )


def test_regrade_confirmed_is_rejected(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.llm = FakeClient()
    service.config = CONFIG
    session = service.start(3)
    question_id = session.question_ids[0]
    service.save_draft(session.id, question_id, "答案")
    suggestion = service.grade(session.id, question_id)
    service.confirm(session.id, question_id, confirm_scores(suggestion, 0.6))
    with pytest.raises(SessionError, match="已确认"):
        service.grade(session.id, question_id)
    assert service.evidence_store.count() == 1
    assert service.answers(session.id)[question_id].status == "confirmed"


def test_confirm_retry_after_completion_returns_same_id(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.llm = FakeClient()
    service.config = CONFIG
    session = service.start(3)
    last_id = ""
    for question_id in session.question_ids:
        service.save_draft(session.id, question_id, "答案")
        suggestion = service.grade(session.id, question_id)
        last_id = service.confirm(
            session.id, question_id, confirm_scores(suggestion, 0.6)
        )
    assert service.get(session.id).status == "completed"
    assert service.confirm(session.id, session.question_ids[-1], []) == last_id
    assert service.evidence_store.count() == 3


def test_confirm_preserves_llm_fields(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.llm = FakeClient()
    service.config = CONFIG
    session = service.start(3)
    question_id = session.question_ids[0]
    service.save_draft(session.id, question_id, "答案")
    suggestion = service.grade(session.id, question_id)
    service.confirm(session.id, question_id, confirm_scores(suggestion, 0.6))
    answer = service.answers(session.id)[question_id]
    assert answer.answer == "答案"
    assert answer.llm_model == "fake"
    assert answer.llm_summary == "继续"
    assert answer.llm_scores


def test_abandon_does_not_demote_completed(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.llm = FakeClient()
    service.config = CONFIG
    session = service.start(3)
    for question_id in session.question_ids:
        service.save_draft(session.id, question_id, "答案")
        suggestion = service.grade(session.id, question_id)
        service.confirm(session.id, question_id, confirm_scores(suggestion, 0.6))
    service.abandon(session.id)
    assert service.get(session.id).status == "completed"
