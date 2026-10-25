"""Orchestrate post-submission review and reference scoring."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace

from testbridge.content.repository import ContentPack
from testbridge.evidence.store import EvidenceEvent, EvidenceStore, new_event
from testbridge.tutor.client import LlmClient
from testbridge.tutor.config import TutorConfig
from testbridge.tutor.review import (
    REVIEW_SYSTEM_PROMPT,
    TutorReview,
    build_review_context,
    parse_review,
    render_review_prompt,
)
from testbridge.tutor.review_store import ExerciseReviewStore, to_review

PROMPT_VERSION = "review/1"
SUPPORTED_KINDS = ("exercise_attempt", "self_assess")


class EvidenceNotFoundError(Exception):
    """The evidence is missing or belongs to another learner."""


class UnsupportedEvidenceError(Exception):
    """The evidence cannot be reviewed (wrong kind or unknown exercise)."""


@dataclass(frozen=True)
class ReviewReply:
    review: TutorReview
    cached: bool
    saved: bool
    evidence_event: EvidenceEvent | None


class ReviewService:
    def __init__(
        self,
        pack: ContentPack,
        evidence: EvidenceStore,
        reviews: ExerciseReviewStore,
        client: LlmClient,
        config: TutorConfig,
        learner_id: str = "local",
    ) -> None:
        self.pack = pack
        self.evidence = evidence
        self.reviews = reviews
        self.client = client
        self.config = config
        self.learner_id = learner_id

    def review(self, evidence_id: str, refresh: bool = False) -> ReviewReply:
        event = self.evidence.get(evidence_id)
        if event is None or event.learner_id != self.learner_id:
            raise EvidenceNotFoundError(evidence_id)
        if event.kind not in SUPPORTED_KINDS:
            raise UnsupportedEvidenceError(event.kind)
        exercise = self.pack.exercises.get(event.exercise_id or "")
        if exercise is None:
            raise UnsupportedEvidenceError(f"unknown exercise: {event.exercise_id}")

        if not refresh:
            stored = self.reviews.get(evidence_id)
            if stored is not None:
                return ReviewReply(
                    review=to_review(stored), cached=True, saved=True,
                    evidence_event=None,
                )

        context = build_review_context(self.pack, event)
        raw = self.client.complete(REVIEW_SYSTEM_PROMPT, render_review_prompt(context))
        review = parse_review(raw, context.dimensions)

        saved = True
        try:
            self.reviews.put(
                evidence_id=evidence_id,
                learner_id=self.learner_id,
                lesson_id=context.lesson_id,
                exercise_id=context.exercise_id,
                review=review,
                model=self.config.model,
                prompt_version=PROMPT_VERSION,
            )
        except sqlite3.Error:
            saved = False

        evidence_event = None
        if context.dimensions and review.suggested_score is not None:
            evidence_event = new_event(
                kind="llm_review",
                lesson_id=event.lesson_id,
                exercise_id=event.exercise_id,
                concept_ids=exercise.concepts,
                outcome="submitted",
                score=review.suggested_score,
                max_score=1.0,
                payload={
                    "evidence_id": evidence_id,
                    "model": self.config.model,
                    "prompt_version": PROMPT_VERSION,
                    "verdict": review.verdict,
                    "rubric": [
                        {"dimension": item.dimension, "met": item.met,
                         "comment": item.comment}
                        for item in review.rubric
                    ],
                },
                source="tutor",
                learner_id=self.learner_id,
            )
            previous = self._previous_review(evidence_id)
            if previous is not None:
                evidence_event = replace(evidence_event, supersedes=previous.id)

        return ReviewReply(
            review=review, cached=False, saved=saved,
            evidence_event=evidence_event,
        )

    def _previous_review(self, evidence_id: str) -> EvidenceEvent | None:
        rows = self.evidence.list(kind="llm_review", limit=1_000)
        matches = [
            row for row in rows
            if row.payload.get("evidence_id") == evidence_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda row: (row.created_at, row.id))
