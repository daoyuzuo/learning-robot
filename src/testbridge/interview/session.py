"""Interview session orchestration: draw, state, scoring, evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from testbridge.content.repository import ContentPack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.interview.bank import InterviewBank, InterviewQuestion
from testbridge.interview.draw import draw_questions
from testbridge.interview.scoring import (
    GradeSuggestion,
    grade_with_llm,
    total_score,
    validate_confirmed_scores,
)
from testbridge.interview.store import (
    InterviewAnswer,
    InterviewSession,
    InterviewStore,
)
from testbridge.learning.service import LearningService
from testbridge.tutor.client import LlmClient
from testbridge.tutor.config import TutorConfig

MAX_ANSWER_CHARS = 10000
QUESTION_COUNTS = (3, 5)


class SessionError(Exception):
    """Invalid session state or request."""


@dataclass(frozen=True)
class SessionSummary:
    session: InterviewSession
    answers: list[InterviewAnswer]
    total: float
    dimension_averages: dict[str, float] = field(default_factory=dict)
    weakest_concepts: list[str] = field(default_factory=list)
    question_totals: dict[str, float] = field(default_factory=dict)


class InterviewService:
    def __init__(
        self,
        pack: ContentPack,
        bank: InterviewBank,
        store: InterviewStore,
        evidence_store: EvidenceStore,
        learning: LearningService,
        llm: LlmClient | None = None,
        config: TutorConfig | None = None,
        learner_id: str = "local",
    ) -> None:
        self.pack = pack
        self.bank = bank
        self.store = store
        self.evidence_store = evidence_store
        self.learning = learning
        self.llm = llm
        self.config = config
        self.learner_id = learner_id

    def start(
        self,
        question_count: int = 3,
        concept_ids: list[str] | None = None,
    ) -> InterviewSession:
        if question_count not in QUESTION_COUNTS:
            raise SessionError("题量只能是 3 或 5")
        mastery = {
            concept_id: view.estimate
            for concept_id, view in self.learning.all_mastery().items()
        }
        weights = {
            concept_id: concept.weight
            for concept_id, concept in self.pack.concepts.items()
        }
        session_id = uuid4().hex
        questions = draw_questions(
            self.bank,
            concept_weights=weights,
            mastery=mastery,
            count=question_count,
            concept_ids=concept_ids,
            seed=session_id,
        )
        if not questions:
            raise SessionError("题库为空")
        session = self.store.create_session(
            learner_id=self.learner_id,
            pack_id=self.pack.meta.id,
            question_ids=[question.id for question in questions],
            concept_ids=list(dict.fromkeys(
                cid for question in questions for cid in question.concepts
            )),
            session_id=session_id,
        )
        return session

    def get(self, session_id: str) -> InterviewSession:
        session = self.store.get_session(session_id)
        if session is None:
            raise SessionError("会话不存在")
        return session

    def answers(self, session_id: str) -> dict[str, InterviewAnswer]:
        return self.store.list_answers(session_id)

    def save_draft(
        self, session_id: str, question_id: str, answer: str
    ) -> InterviewAnswer:
        session = self._running(session_id)
        question = self._question(session, question_id)
        if len(answer) > MAX_ANSWER_CHARS:
            raise SessionError(f"回答不能超过 {MAX_ANSWER_CHARS} 字符")
        existing = self.store.get_answer(session_id, question_id)
        if existing and existing.status in {"graded", "confirmed"}:
            raise SessionError("答案已评分，请先重新作答")
        saved = InterviewAnswer(
            session_id=session_id,
            question_id=question.id,
            answer=answer,
            status="answered",
        )
        self.store.save_answer(saved)
        return saved

    def reset_answer(self, session_id: str, question_id: str) -> InterviewAnswer:
        session = self._running(session_id)
        self._question(session, question_id)
        existing = self.store.get_answer(session_id, question_id)
        if existing and existing.status == "confirmed":
            raise SessionError("该题已确认，不能重新作答")
        reset = InterviewAnswer(
            session_id=session_id, question_id=question_id, answer="",
            status="answered",
        )
        self.store.save_answer(reset)
        return reset

    def _running(self, session_id: str) -> InterviewSession:
        session = self.get(session_id)
        if session.status != "running":
            raise SessionError("会话已结束")
        return session

    def _question(
        self, session: InterviewSession, question_id: str
    ) -> InterviewQuestion:
        if question_id not in session.question_ids:
            raise SessionError("题目不属于本次会话")
        return self.bank.by_id(question_id)
