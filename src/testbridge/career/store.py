"""SQLite storage for the single target JD (never evidence)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from testbridge.learning.timeutil import iso, utcnow

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS target_jd (
  learner_id        TEXT PRIMARY KEY,
  source_text       TEXT NOT NULL,
  target_role       TEXT NOT NULL DEFAULT '',
  requirements_json TEXT NOT NULL DEFAULT '[]',
  weights_json      TEXT NOT NULL DEFAULT '{}',
  model             TEXT,
  updated_at        TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class TargetJd:
    learner_id: str
    source_text: str
    target_role: str = ""
    requirements: list[dict] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    model: str | None = None
    updated_at: str = ""


class TargetJdStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA_SQL)

    def get(self, learner_id: str = "local") -> TargetJd | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM target_jd WHERE learner_id = ?", (learner_id,)
            ).fetchone()
        return self._row_to_target(row) if row else None

    def save(self, target: TargetJd) -> TargetJd:
        saved = TargetJd(
            learner_id=target.learner_id,
            source_text=target.source_text,
            target_role=target.target_role,
            requirements=list(target.requirements),
            weights=dict(target.weights),
            model=target.model,
            updated_at=iso(utcnow()),
        )
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO target_jd
                (learner_id, source_text, target_role, requirements_json,
                 weights_json, model, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(learner_id) DO UPDATE SET
                  source_text=excluded.source_text,
                  target_role=excluded.target_role,
                  requirements_json=excluded.requirements_json,
                  weights_json=excluded.weights_json,
                  model=excluded.model,
                  updated_at=excluded.updated_at
                """,
                (
                    saved.learner_id, saved.source_text, saved.target_role,
                    json.dumps(saved.requirements, ensure_ascii=False),
                    json.dumps(saved.weights, ensure_ascii=False),
                    saved.model, saved.updated_at,
                ),
            )
        return saved

    def count(self) -> int:
        with sqlite3.connect(self.path) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM target_jd").fetchone()[0])

    @staticmethod
    def _row_to_target(row: sqlite3.Row) -> TargetJd:
        return TargetJd(
            learner_id=row["learner_id"],
            source_text=row["source_text"],
            target_role=row["target_role"],
            requirements=json.loads(row["requirements_json"] or "[]"),
            weights=json.loads(row["weights_json"] or "{}"),
            model=row["model"],
            updated_at=row["updated_at"],
        )
