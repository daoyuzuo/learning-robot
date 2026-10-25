"""Cache of AI reviews keyed by the evidence they comment on."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from testbridge.learning.timeutil import iso, utcnow
from testbridge.tutor.review import RubricVerdict, TutorReview

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS exercise_review (
  evidence_id     TEXT PRIMARY KEY,
  learner_id      TEXT NOT NULL,
  lesson_id       TEXT NOT NULL,
  exercise_id     TEXT NOT NULL,
  verdict         TEXT NOT NULL,
  explanation     TEXT NOT NULL,
  strengths_json  TEXT NOT NULL DEFAULT '[]',
  gaps_json       TEXT NOT NULL DEFAULT '[]',
  rubric_json     TEXT NOT NULL DEFAULT '[]',
  suggested_score REAL,
  model           TEXT NOT NULL,
  prompt_version  TEXT NOT NULL,
  created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_exercise
  ON exercise_review(learner_id, exercise_id);
"""


@dataclass(frozen=True)
class StoredReview:
    evidence_id: str
    learner_id: str
    lesson_id: str
    exercise_id: str
    verdict: str
    explanation: str
    strengths: list[str]
    gaps: list[str]
    rubric: list[RubricVerdict]
    suggested_score: float | None
    model: str
    prompt_version: str
    created_at: str


class ExerciseReviewStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA_SQL)

    def put(
        self,
        *,
        evidence_id: str,
        learner_id: str,
        lesson_id: str,
        exercise_id: str,
        review: TutorReview,
        model: str,
        prompt_version: str,
    ) -> StoredReview:
        stored = StoredReview(
            evidence_id=evidence_id,
            learner_id=learner_id,
            lesson_id=lesson_id,
            exercise_id=exercise_id,
            verdict=review.verdict,
            explanation=review.explanation,
            strengths=list(review.strengths),
            gaps=list(review.gaps),
            rubric=list(review.rubric),
            suggested_score=review.suggested_score,
            model=model,
            prompt_version=prompt_version,
            created_at=iso(utcnow()),
        )
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO exercise_review
                (evidence_id, learner_id, lesson_id, exercise_id, verdict,
                 explanation, strengths_json, gaps_json, rubric_json,
                 suggested_score, model, prompt_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(evidence_id) DO UPDATE SET
                  learner_id=excluded.learner_id,
                  lesson_id=excluded.lesson_id,
                  exercise_id=excluded.exercise_id,
                  verdict=excluded.verdict,
                  explanation=excluded.explanation,
                  strengths_json=excluded.strengths_json,
                  gaps_json=excluded.gaps_json,
                  rubric_json=excluded.rubric_json,
                  suggested_score=excluded.suggested_score,
                  model=excluded.model,
                  prompt_version=excluded.prompt_version,
                  created_at=excluded.created_at
                """,
                (
                    stored.evidence_id, stored.learner_id, stored.lesson_id,
                    stored.exercise_id, stored.verdict, stored.explanation,
                    json.dumps(stored.strengths, ensure_ascii=False),
                    json.dumps(stored.gaps, ensure_ascii=False),
                    json.dumps(
                        [
                            {"dimension": item.dimension, "met": item.met,
                             "comment": item.comment}
                            for item in stored.rubric
                        ],
                        ensure_ascii=False,
                    ),
                    stored.suggested_score, stored.model,
                    stored.prompt_version, stored.created_at,
                ),
            )
        return stored

    def get(self, evidence_id: str) -> StoredReview | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM exercise_review WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
        if row is None:
            return None
        return StoredReview(
            evidence_id=row["evidence_id"],
            learner_id=row["learner_id"],
            lesson_id=row["lesson_id"],
            exercise_id=row["exercise_id"],
            verdict=row["verdict"],
            explanation=row["explanation"],
            strengths=json.loads(row["strengths_json"]),
            gaps=json.loads(row["gaps_json"]),
            rubric=[
                RubricVerdict(item["dimension"], item["met"], item["comment"])
                for item in json.loads(row["rubric_json"])
            ],
            suggested_score=row["suggested_score"],
            model=row["model"],
            prompt_version=row["prompt_version"],
            created_at=row["created_at"],
        )


def to_review(stored: StoredReview) -> TutorReview:
    return TutorReview(
        verdict=stored.verdict,
        explanation=stored.explanation,
        strengths=list(stored.strengths),
        gaps=list(stored.gaps),
        rubric=list(stored.rubric),
        suggested_score=stored.suggested_score,
    )
