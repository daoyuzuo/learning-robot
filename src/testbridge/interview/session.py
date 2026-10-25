"""Interview session orchestration: draw, state, scoring, evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from testbridge.content.repository import ContentPack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.interview.bank import InterviewBank, InterviewQuestion
from testbridge.interview.draw import draw_questions
from testbridge.interview.scoring import (
    DimensionScore,
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

    def grade(self, session_id: str, question_id: str) -> GradeSuggestion:
        session = self._running(session_id)
        question = self._question(session, question_id)
        answer = self.store.get_answer(session_id, question_id)
        if answer is None or not answer.answer.strip():
            raise SessionError("请先作答")
        if answer.status == "confirmed":
            raise SessionError("该题已确认，不能重新评分")
        suggestion = grade_with_llm(
            self.llm, self.config, question, answer.answer, self.pack.concepts
        )
        self.store.save_answer(
            InterviewAnswer(
                session_id=session_id,
                question_id=question_id,
                answer=answer.answer,
                status="graded",
                llm_scores=[
                    {
                        "dimension": item.dimension,
                        "weight": item.weight,
                        "score": item.score,
                        "rationale": item.rationale,
                    }
                    for item in suggestion.scores
                ],
                llm_summary=suggestion.summary,
                llm_model=suggestion.model,
            )
        )
        return suggestion

    def confirm(
        self,
        session_id: str,
        question_id: str,
        scores: list[dict],
        duration_ms: int = 0,
    ) -> str:
        session = self.get(session_id)
        question = self._question(session, question_id)
        answer = self.store.get_answer(session_id, question_id)
        if answer is None:
            raise SessionError("请先作答")
        if answer.evidence_id:
            return answer.evidence_id
        if session.status != "running":
            raise SessionError("会话已结束")
        if answer.status != "graded":
            raise SessionError("请先完成评分")

        confirmed = validate_confirmed_scores(question, scores)
        total = total_score(confirmed)
        event = new_event(
            kind="interview",
            concept_ids=list(question.concepts),
            session_id=session_id,
            outcome="submitted",
            score=total,
            max_score=1.0,
            payload={
                "question_id": question.id,
                "title": question.title,
                "answer": answer.answer,
                "duration_ms": max(0, int(duration_ms)),
                "scores": [
                    {
                        "dimension": item.dimension,
                        "weight": item.weight,
                        "score": item.score,
                    }
                    for item in confirmed
                ],
                "llm": {
                    "model": answer.llm_model,
                    "scores": answer.llm_scores,
                    "summary": answer.llm_summary,
                },
                "reviewed_by_user": True,
            },
            source="web",
            learner_id=self.learner_id,
        )
        self.evidence_store.append(event)
        self.learning.record(event)

        self.store.save_answer(
            InterviewAnswer(
                session_id=session_id,
                question_id=question_id,
                answer=answer.answer,
                status="confirmed",
                llm_scores=answer.llm_scores,
                llm_summary=answer.llm_summary,
                llm_model=answer.llm_model,
                confirmed_scores=[
                    {
                        "dimension": item.dimension,
                        "weight": item.weight,
                        "score": item.score,
                    }
                    for item in confirmed
                ],
                evidence_id=event.id,
            )
        )

        answers = self.store.list_answers(session_id)
        confirmed_ids = {
            item_id for item_id, item in answers.items() if item.status == "confirmed"
        }
        if len(confirmed_ids) >= len(session.question_ids):
            self.store.update_session(
                InterviewSession(
                    id=session.id, learner_id=session.learner_id,
                    pack_id=session.pack_id, status="completed",
                    question_ids=session.question_ids,
                    concept_ids=session.concept_ids,
                    current_index=len(session.question_ids),
                    created_at=session.created_at, updated_at=session.updated_at,
                )
            )
        else:
            next_index = next(
                index for index, item_id in enumerate(session.question_ids)
                if item_id not in confirmed_ids
            )
            self.store.update_session(
                InterviewSession(
                    id=session.id, learner_id=session.learner_id,
                    pack_id=session.pack_id, status="running",
                    question_ids=session.question_ids,
                    concept_ids=session.concept_ids,
                    current_index=next_index,
                    created_at=session.created_at, updated_at=session.updated_at,
                )
            )
        return event.id

    def abandon(self, session_id: str) -> None:
        session = self.get(session_id)
        if session.status in {"abandoned", "completed"}:
            return
        self.store.update_session(
            InterviewSession(
                id=session.id, learner_id=session.learner_id,
                pack_id=session.pack_id, status="abandoned",
                question_ids=session.question_ids,
                concept_ids=session.concept_ids,
                current_index=session.current_index,
                created_at=session.created_at, updated_at=session.updated_at,
            )
        )

    def summary(self, session_id: str) -> SessionSummary:
        session = self.get(session_id)
        answers = [
            self.store.get_answer(session_id, question_id)
            for question_id in session.question_ids
        ]
        existing = [item for item in answers if item is not None]
        confirmed = [item for item in existing if item.status == "confirmed"]
        per_question = [self.question_total(item) for item in confirmed]
        totals: dict[str, list[float]] = {}
        weakest: list[str] = []
        for item, question_total in zip(confirmed, per_question):
            for score in item.confirmed_scores:
                totals.setdefault(score["dimension"], []).append(float(score["score"]))
            if question_total < 0.5:
                question = self.bank.by_id(item.question_id)
                for concept_id in question.concepts:
                    if concept_id not in weakest:
                        weakest.append(concept_id)
        return SessionSummary(
            session=session,
            answers=existing,
            total=round(sum(per_question) / len(per_question), 3)
            if per_question else 0.0,
            dimension_averages={
                dimension: round(sum(values) / len(values), 3)
                for dimension, values in totals.items()
            },
            weakest_concepts=weakest,
            question_totals={
                item.question_id: value
                for item, value in zip(confirmed, per_question)
            },
        )

    @staticmethod
    def question_total(answer: InterviewAnswer) -> float:
        return total_score([
            DimensionScore(
                dimension=score["dimension"],
                weight=float(score["weight"]),
                score=float(score["score"]),
            )
            for score in answer.confirmed_scores
        ])
