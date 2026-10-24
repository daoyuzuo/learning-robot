"""Append-only SQLite evidence store."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS evidence (
  id TEXT PRIMARY KEY,
  learner_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  session_id TEXT,
  lesson_id TEXT,
  exercise_id TEXT,
  concept_ids TEXT NOT NULL,
  outcome TEXT,
  score REAL,
  max_score REAL,
  payload TEXT NOT NULL,
  source TEXT NOT NULL,
  created_at TEXT NOT NULL,
  supersedes TEXT
);
CREATE INDEX IF NOT EXISTS idx_evidence_lesson ON evidence(lesson_id);
CREATE INDEX IF NOT EXISTS idx_evidence_created ON evidence(created_at);
"""


@dataclass(frozen=True)
class EvidenceEvent:
    id: str
    learner_id: str
    kind: str
    concept_ids: list[str]
    payload: dict[str, Any]
    source: str
    created_at: str
    session_id: str | None = None
    lesson_id: str | None = None
    exercise_id: str | None = None
    outcome: str | None = None
    score: float | None = None
    max_score: float | None = None
    supersedes: str | None = None


def new_event(
    *,
    kind: str,
    concept_ids: list[str],
    lesson_id: str | None = None,
    exercise_id: str | None = None,
    outcome: str | None = None,
    score: float | None = None,
    max_score: float | None = None,
    payload: dict[str, Any] | None = None,
    source: str = "web",
    session_id: str | None = None,
    learner_id: str = "local",
) -> EvidenceEvent:
    return EvidenceEvent(
        id=uuid4().hex,
        learner_id=learner_id,
        kind=kind,
        concept_ids=concept_ids,
        payload=payload or {},
        source=source,
        created_at=datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
        lesson_id=lesson_id,
        exercise_id=exercise_id,
        outcome=outcome,
        score=score,
        max_score=max_score,
    )


class EvidenceStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA_SQL)

    def append(self, event: EvidenceEvent) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO evidence
                (id, learner_id, kind, session_id, lesson_id, exercise_id,
                 concept_ids, outcome, score, max_score, payload, source,
                 created_at, supersedes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id, event.learner_id, event.kind, event.session_id,
                    event.lesson_id, event.exercise_id,
                    json.dumps(event.concept_ids, ensure_ascii=False),
                    event.outcome, event.score, event.max_score,
                    json.dumps(event.payload, ensure_ascii=False),
                    event.source, event.created_at, event.supersedes,
                ),
            )

    def list(
        self,
        lesson_id: str | None = None,
        concept_id: str | None = None,
        limit: int = 100,
    ) -> list[EvidenceEvent]:
        sql = "SELECT * FROM evidence WHERE 1=1"
        params: list[Any] = []
        if lesson_id:
            sql += " AND lesson_id = ?"
            params.append(lesson_id)
        if concept_id:
            sql += " AND concept_ids LIKE ?"
            params.append(f'%"{concept_id}"%')
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def count(self, lesson_id: str | None = None) -> int:
        sql = "SELECT COUNT(*) FROM evidence"
        params: list[Any] = []
        if lesson_id:
            sql += " WHERE lesson_id = ?"
            params.append(lesson_id)
        with sqlite3.connect(self.path) as conn:
            return int(conn.execute(sql, params).fetchone()[0])

    def export_jsonl(self, path: Path) -> int:
        events = self.list(limit=1_000_000)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return len(events)

    def import_jsonl(self, path: Path) -> int:
        inserted = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = EvidenceEvent(**json.loads(line))
            before = self.count()
            self.append(event)
            if self.count() > before:
                inserted += 1
        return inserted

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> EvidenceEvent:
        return EvidenceEvent(
            id=row["id"],
            learner_id=row["learner_id"],
            kind=row["kind"],
            concept_ids=json.loads(row["concept_ids"]),
            payload=json.loads(row["payload"]),
            source=row["source"],
            created_at=row["created_at"],
            session_id=row["session_id"],
            lesson_id=row["lesson_id"],
            exercise_id=row["exercise_id"],
            outcome=row["outcome"],
            score=row["score"],
            max_score=row["max_score"],
            supersedes=row["supersedes"],
        )
