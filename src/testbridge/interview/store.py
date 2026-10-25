"""SQLite storage for interview sessions and answers (never evidence)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from testbridge.learning.timeutil import iso, utcnow

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS interview_session (
  id            TEXT PRIMARY KEY,
  learner_id    TEXT NOT NULL,
  pack_id       TEXT NOT NULL,
  status        TEXT NOT NULL,
  question_ids  TEXT NOT NULL,
  concept_ids   TEXT NOT NULL,
  current_index INTEGER NOT NULL,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interview_session_learner
  ON interview_session(learner_id, created_at);

CREATE TABLE IF NOT EXISTS interview_answer (
  session_id       TEXT NOT NULL,
  question_id      TEXT NOT NULL,
  answer           TEXT NOT NULL DEFAULT '',
  status           TEXT NOT NULL,
  llm_scores       TEXT,
  llm_summary      TEXT,
  llm_model        TEXT,
  confirmed_scores TEXT,
  evidence_id      TEXT,
  updated_at       TEXT NOT NULL,
  PRIMARY KEY (session_id, question_id)
);
"""


@dataclass(frozen=True)
class InterviewSession:
    id: str
    learner_id: str
    pack_id: str
    status: str
    question_ids: list[str]
    concept_ids: list[str]
    current_index: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class InterviewAnswer:
    session_id: str
    question_id: str
    answer: str = ""
    status: str = "answered"
    llm_scores: list[dict] = field(default_factory=list)
    llm_summary: str = ""
    llm_model: str | None = None
    confirmed_scores: list[dict] = field(default_factory=list)
    evidence_id: str | None = None
    updated_at: str = ""


class InterviewStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA_SQL)

    def create_session(
        self,
        *,
        learner_id: str,
        pack_id: str,
        question_ids: list[str],
        concept_ids: list[str],
        session_id: str | None = None,
    ) -> InterviewSession:
        now = iso(utcnow())
        session = InterviewSession(
            id=session_id or uuid4().hex,
            learner_id=learner_id,
            pack_id=pack_id,
            status="running",
            question_ids=list(question_ids),
            concept_ids=list(concept_ids),
            current_index=0,
            created_at=now,
            updated_at=now,
        )
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO interview_session
                (id, learner_id, pack_id, status, question_ids, concept_ids,
                 current_index, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id, session.learner_id, session.pack_id,
                    session.status,
                    json.dumps(session.question_ids, ensure_ascii=False),
                    json.dumps(session.concept_ids, ensure_ascii=False),
                    session.current_index, session.created_at, session.updated_at,
                ),
            )
        return session

    def get_session(self, session_id: str) -> InterviewSession | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM interview_session WHERE id = ?", (session_id,)
            ).fetchone()
        return self._row_to_session(row) if row else None

    def list_sessions(self, learner_id: str, limit: int = 5) -> list[InterviewSession]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM interview_session
                WHERE learner_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (learner_id, limit),
            ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def update_session(self, session: InterviewSession) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                UPDATE interview_session
                SET status = ?, current_index = ?, updated_at = ?
                WHERE id = ?
                """,
                (session.status, session.current_index, iso(utcnow()), session.id),
            )

    def get_answer(self, session_id: str, question_id: str) -> InterviewAnswer | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM interview_answer
                WHERE session_id = ? AND question_id = ?
                """,
                (session_id, question_id),
            ).fetchone()
        return self._row_to_answer(row) if row else None

    def list_answers(self, session_id: str) -> dict[str, InterviewAnswer]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM interview_answer WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        return {row["question_id"]: self._row_to_answer(row) for row in rows}

    def save_answer(self, answer: InterviewAnswer) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO interview_answer
                (session_id, question_id, answer, status, llm_scores,
                 llm_summary, llm_model, confirmed_scores, evidence_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, question_id) DO UPDATE SET
                  answer=excluded.answer,
                  status=excluded.status,
                  llm_scores=excluded.llm_scores,
                  llm_summary=excluded.llm_summary,
                  llm_model=excluded.llm_model,
                  confirmed_scores=excluded.confirmed_scores,
                  evidence_id=excluded.evidence_id,
                  updated_at=excluded.updated_at
                """,
                (
                    answer.session_id, answer.question_id, answer.answer,
                    answer.status,
                    json.dumps(answer.llm_scores, ensure_ascii=False),
                    answer.llm_summary, answer.llm_model,
                    json.dumps(answer.confirmed_scores, ensure_ascii=False),
                    answer.evidence_id, iso(utcnow()),
                ),
            )

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> InterviewSession:
        return InterviewSession(
            id=row["id"], learner_id=row["learner_id"], pack_id=row["pack_id"],
            status=row["status"],
            question_ids=json.loads(row["question_ids"]),
            concept_ids=json.loads(row["concept_ids"]),
            current_index=row["current_index"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_answer(row: sqlite3.Row) -> InterviewAnswer:
        return InterviewAnswer(
            session_id=row["session_id"], question_id=row["question_id"],
            answer=row["answer"], status=row["status"],
            llm_scores=json.loads(row["llm_scores"] or "[]"),
            llm_summary=row["llm_summary"] or "",
            llm_model=row["llm_model"],
            confirmed_scores=json.loads(row["confirmed_scores"] or "[]"),
            evidence_id=row["evidence_id"],
            updated_at=row["updated_at"],
        )
