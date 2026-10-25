"""SQLite storage for derived learning state and the learner goal."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .timeutil import iso

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mastery_state (
  learner_id TEXT NOT NULL,
  concept_id TEXT NOT NULL,
  rule_score REAL NOT NULL,
  bkt_p REAL NOT NULL,
  exercise_observations INTEGER NOT NULL,
  other_observations INTEGER NOT NULL,
  estimate REAL NOT NULL,
  confidence REAL NOT NULL,
  level TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (learner_id, concept_id)
);

CREATE TABLE IF NOT EXISTS review_state (
  learner_id TEXT NOT NULL,
  exercise_id TEXT NOT NULL,
  concept_ids TEXT NOT NULL,
  due TEXT NOT NULL,
  stability REAL NOT NULL,
  difficulty REAL NOT NULL,
  reps INTEGER NOT NULL,
  lapses INTEGER NOT NULL,
  state TEXT NOT NULL,
  last_review TEXT,
  card_json TEXT NOT NULL,
  PRIMARY KEY (learner_id, exercise_id)
);

CREATE TABLE IF NOT EXISTS goal (
  learner_id TEXT PRIMARY KEY,
  target_role TEXT NOT NULL DEFAULT '',
  weekly_hours REAL NOT NULL DEFAULT 0,
  daily_minutes INTEGER NOT NULL DEFAULT 45,
  concept_overrides_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Goal:
    learner_id: str = "local"
    target_role: str = ""
    weekly_hours: float = 0.0
    daily_minutes: int = 45
    concept_overrides: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class MasteryState:
    learner_id: str
    concept_id: str
    rule_score: float
    bkt_p: float
    exercise_observations: int
    other_observations: int
    estimate: float
    confidence: float
    level: str
    updated_at: str


@dataclass(frozen=True)
class ReviewState:
    learner_id: str
    exercise_id: str
    concept_ids: list[str]
    due: str
    stability: float
    difficulty: float
    reps: int
    lapses: int
    state: str
    last_review: str | None
    card_json: dict[str, Any]


class LearningStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA_SQL)

    def get_goal(self, learner_id: str = "local") -> Goal:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM goal WHERE learner_id = ?", (learner_id,)).fetchone()
        if row is None:
            return Goal(learner_id=learner_id)
        return Goal(
            learner_id=row["learner_id"],
            target_role=row["target_role"],
            weekly_hours=row["weekly_hours"],
            daily_minutes=row["daily_minutes"],
            concept_overrides=json.loads(row["concept_overrides_json"]),
        )

    def set_goal(self, goal: Goal) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO goal
                (learner_id, target_role, weekly_hours, daily_minutes,
                 concept_overrides_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(learner_id) DO UPDATE SET
                  target_role=excluded.target_role,
                  weekly_hours=excluded.weekly_hours,
                  daily_minutes=excluded.daily_minutes,
                  concept_overrides_json=excluded.concept_overrides_json,
                  updated_at=excluded.updated_at
                """,
                (
                    goal.learner_id, goal.target_role, goal.weekly_hours,
                    goal.daily_minutes,
                    json.dumps(goal.concept_overrides, ensure_ascii=False),
                    iso(datetime.now().astimezone()),
                ),
            )

    def get_mastery(self, learner_id: str, concept_id: str) -> MasteryState | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM mastery_state WHERE learner_id = ? AND concept_id = ?",
                (learner_id, concept_id),
            ).fetchone()
        return self._row_to_mastery(row) if row else None

    def upsert_mastery(self, state: MasteryState) -> None:
        with sqlite3.connect(self.path) as conn:
            self._insert_mastery(conn, state)

    def list_mastery(self, learner_id: str) -> dict[str, MasteryState]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM mastery_state WHERE learner_id = ?", (learner_id,)
            ).fetchall()
        return {row["concept_id"]: self._row_to_mastery(row) for row in rows}

    def clear_mastery(self, learner_id: str) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM mastery_state WHERE learner_id = ?", (learner_id,))

    def get_review(self, learner_id: str, exercise_id: str) -> ReviewState | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM review_state WHERE learner_id = ? AND exercise_id = ?",
                (learner_id, exercise_id),
            ).fetchone()
        return self._row_to_review(row) if row else None

    def upsert_review(self, state: ReviewState) -> None:
        with sqlite3.connect(self.path) as conn:
            self._insert_review(conn, state)

    def list_reviews(self, learner_id: str) -> dict[str, ReviewState]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM review_state WHERE learner_id = ?", (learner_id,)
            ).fetchall()
        return {row["exercise_id"]: self._row_to_review(row) for row in rows}

    def due_reviews(self, learner_id: str, now: datetime) -> list[ReviewState]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM review_state
                WHERE learner_id = ? AND due <= ?
                ORDER BY due, exercise_id
                """,
                (learner_id, iso(now)),
            ).fetchall()
        return [self._row_to_review(row) for row in rows]

    def clear_reviews(self, learner_id: str) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM review_state WHERE learner_id = ?", (learner_id,))

    def replace_all(
        self,
        learner_id: str,
        mastery: dict[str, MasteryState],
        reviews: dict[str, ReviewState],
    ) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM mastery_state WHERE learner_id = ?", (learner_id,))
            conn.execute("DELETE FROM review_state WHERE learner_id = ?", (learner_id,))
            for state in mastery.values():
                self._insert_mastery(conn, state)
            for review in reviews.values():
                self._insert_review(conn, review)

    @staticmethod
    def _insert_mastery(conn: sqlite3.Connection, state: MasteryState) -> None:
        conn.execute(
            """
            INSERT INTO mastery_state
            (learner_id, concept_id, rule_score, bkt_p, exercise_observations,
             other_observations, estimate, confidence, level, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(learner_id, concept_id) DO UPDATE SET
              rule_score=excluded.rule_score,
              bkt_p=excluded.bkt_p,
              exercise_observations=excluded.exercise_observations,
              other_observations=excluded.other_observations,
              estimate=excluded.estimate,
              confidence=excluded.confidence,
              level=excluded.level,
              updated_at=excluded.updated_at
            """,
            (
                state.learner_id, state.concept_id, state.rule_score, state.bkt_p,
                state.exercise_observations, state.other_observations,
                state.estimate, state.confidence, state.level, state.updated_at,
            ),
        )

    @staticmethod
    def _insert_review(conn: sqlite3.Connection, review: ReviewState) -> None:
        conn.execute(
            """
            INSERT INTO review_state
            (learner_id, exercise_id, concept_ids, due, stability, difficulty,
             reps, lapses, state, last_review, card_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(learner_id, exercise_id) DO UPDATE SET
              concept_ids=excluded.concept_ids,
              due=excluded.due,
              stability=excluded.stability,
              difficulty=excluded.difficulty,
              reps=excluded.reps,
              lapses=excluded.lapses,
              state=excluded.state,
              last_review=excluded.last_review,
              card_json=excluded.card_json
            """,
            (
                review.learner_id, review.exercise_id,
                json.dumps(review.concept_ids, ensure_ascii=False),
                review.due, review.stability, review.difficulty,
                review.reps, review.lapses, review.state, review.last_review,
                json.dumps(review.card_json, ensure_ascii=False),
            ),
        )

    @staticmethod
    def _row_to_mastery(row: sqlite3.Row) -> MasteryState:
        return MasteryState(
            learner_id=row["learner_id"], concept_id=row["concept_id"],
            rule_score=row["rule_score"], bkt_p=row["bkt_p"],
            exercise_observations=row["exercise_observations"],
            other_observations=row["other_observations"],
            estimate=row["estimate"], confidence=row["confidence"],
            level=row["level"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_review(row: sqlite3.Row) -> ReviewState:
        return ReviewState(
            learner_id=row["learner_id"], exercise_id=row["exercise_id"],
            concept_ids=json.loads(row["concept_ids"]), due=row["due"],
            stability=row["stability"], difficulty=row["difficulty"],
            reps=row["reps"], lapses=row["lapses"], state=row["state"],
            last_review=row["last_review"], card_json=json.loads(row["card_json"]),
        )
