"""SQLite storage for tutor conversations (never evidence)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from testbridge.learning.timeutil import iso, utcnow

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tutor_message (
  id             TEXT PRIMARY KEY,
  learner_id     TEXT NOT NULL,
  lesson_id      TEXT NOT NULL,
  anchor         TEXT NOT NULL DEFAULT '',
  role           TEXT NOT NULL,
  content        TEXT NOT NULL,
  basis          TEXT,
  citations_json TEXT NOT NULL DEFAULT '[]',
  model          TEXT,
  created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tutor_lesson
  ON tutor_message(learner_id, lesson_id, created_at);
"""


@dataclass(frozen=True)
class TutorMessage:
    id: str
    learner_id: str
    lesson_id: str
    anchor: str
    role: str
    content: str
    basis: str | None
    citations: list[str]
    model: str | None
    created_at: str


class TutorStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA_SQL)

    def append(
        self,
        *,
        learner_id: str,
        lesson_id: str,
        anchor: str,
        role: str,
        content: str,
        basis: str | None = None,
        citations: list[str] | tuple[str, ...] = (),
        model: str | None = None,
    ) -> TutorMessage:
        message = TutorMessage(
            id=uuid4().hex,
            learner_id=learner_id,
            lesson_id=lesson_id,
            anchor=anchor,
            role=role,
            content=content,
            basis=basis,
            citations=list(citations),
            model=model,
            created_at=iso(utcnow()),
        )
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO tutor_message
                (id, learner_id, lesson_id, anchor, role, content, basis,
                 citations_json, model, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id, message.learner_id, message.lesson_id,
                    message.anchor, message.role, message.content, message.basis,
                    json.dumps(message.citations, ensure_ascii=False),
                    message.model, message.created_at,
                ),
            )
        return message

    def history(
        self, learner_id: str, lesson_id: str, limit: int = 20
    ) -> list[TutorMessage]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM tutor_message
                WHERE learner_id = ? AND lesson_id = ?
                ORDER BY rowid DESC
                LIMIT ?
                """,
                (learner_id, lesson_id, limit),
            ).fetchall()
        return [self._row_to_message(row) for row in reversed(rows)]

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> TutorMessage:
        return TutorMessage(
            id=row["id"],
            learner_id=row["learner_id"],
            lesson_id=row["lesson_id"],
            anchor=row["anchor"],
            role=row["role"],
            content=row["content"],
            basis=row["basis"],
            citations=json.loads(row["citations_json"]),
            model=row["model"],
            created_at=row["created_at"],
        )
