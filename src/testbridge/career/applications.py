"""Job application tracking (P4.3)."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from uuid import uuid4

from testbridge.learning.timeutil import iso, utcnow

STATUSES = (
    "draft", "applied", "screening", "interviewing",
    "offer", "rejected", "withdrawn",
)
TERMINAL_STATUSES = frozenset({"offer", "rejected", "withdrawn"})
MAX_COMPANY = 200
MAX_ROLE = 200
MAX_SOURCE = 100
MAX_NEXT_ACTION = 200
MAX_NOTES = 5000
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS application (
  id              TEXT PRIMARY KEY,
  learner_id      TEXT NOT NULL DEFAULT 'local',
  company         TEXT NOT NULL,
  role            TEXT NOT NULL,
  source          TEXT NOT NULL DEFAULT '',
  status          TEXT NOT NULL DEFAULT 'draft',
  applied_at      TEXT,
  next_action_at  TEXT,
  next_action     TEXT NOT NULL DEFAULT '',
  notes           TEXT NOT NULL DEFAULT '',
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_application_learner
  ON application(learner_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_application_due
  ON application(learner_id, next_action_at);
"""


class ApplicationError(Exception):
    """Invalid application data or unknown record."""


@dataclass(frozen=True)
class Application:
    id: str
    learner_id: str
    company: str
    role: str
    source: str = ""
    status: str = "draft"
    applied_at: str | None = None
    next_action_at: str | None = None
    next_action: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


def safe_text(value: str) -> str:
    return value.encode("utf-8", "replace").decode("utf-8")


def _date(value: str | None, *, field: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not DATE_RE.fullmatch(text):
        raise ApplicationError(f"{field}必须是 YYYY-MM-DD")
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ApplicationError(f"{field}必须是 YYYY-MM-DD") from exc
    return text


def clean_fields(
    *,
    company: str,
    role: str,
    source: str = "",
    status: str = "draft",
    applied_at: str | None = None,
    next_action_at: str | None = None,
    next_action: str = "",
    notes: str = "",
) -> dict:
    company = safe_text(company.strip())
    if not company:
        raise ApplicationError("公司不能为空")
    role = safe_text(role.strip())
    if not role:
        raise ApplicationError("岗位不能为空")
    if status not in STATUSES:
        raise ApplicationError(f"状态非法：{status}")
    return {
        "company": company[:MAX_COMPANY],
        "role": role[:MAX_ROLE],
        "source": safe_text(source.strip())[:MAX_SOURCE],
        "status": status,
        "applied_at": _date(applied_at, field="投递日期"),
        "next_action_at": _date(next_action_at, field="跟进日期"),
        "next_action": safe_text(next_action.strip())[:MAX_NEXT_ACTION],
        "notes": safe_text(notes)[:MAX_NOTES],
    }


class ApplicationStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA_SQL)

    def create(
        self,
        *,
        company: str,
        role: str,
        source: str = "",
        status: str = "draft",
        applied_at: str | None = None,
        next_action_at: str | None = None,
        next_action: str = "",
        notes: str = "",
        learner_id: str = "local",
    ) -> Application:
        fields = clean_fields(
            company=company, role=role, source=source, status=status,
            applied_at=applied_at, next_action_at=next_action_at,
            next_action=next_action, notes=notes,
        )
        now = iso(utcnow())
        application = Application(
            id=uuid4().hex, learner_id=learner_id, **fields,
            created_at=now, updated_at=now,
        )
        self._upsert(application)
        return application

    def get(self, app_id: str, learner_id: str = "local") -> Application | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM application WHERE id = ? AND learner_id = ?",
                (app_id, learner_id),
            ).fetchone()
        return self._row_to_application(row) if row else None

    def list(
        self, learner_id: str = "local", status: str | None = None
    ) -> list[Application]:
        sql = "SELECT * FROM application WHERE learner_id = ?"
        params: list = [learner_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC, id"
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_application(row) for row in rows]

    def update(
        self, app_id: str, *, learner_id: str = "local", **changes
    ) -> Application:
        current = self.get(app_id, learner_id)
        if current is None:
            raise ApplicationError("投递记录不存在")
        allowed = {
            "company", "role", "source", "status", "applied_at",
            "next_action_at", "next_action", "notes",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ApplicationError(f"不支持修改的字段：{', '.join(sorted(unknown))}")
        merged = {
            "company": changes.get("company", current.company),
            "role": changes.get("role", current.role),
            "source": changes.get("source", current.source),
            "status": changes.get("status", current.status),
            "applied_at": changes.get("applied_at", current.applied_at),
            "next_action_at": changes.get(
                "next_action_at", current.next_action_at
            ),
            "next_action": changes.get("next_action", current.next_action),
            "notes": changes.get("notes", current.notes),
        }
        updated = replace(
            current,
            **clean_fields(**merged),
            updated_at=iso(utcnow()),
        )
        self._upsert(updated)
        return updated

    def withdraw(self, app_id: str, learner_id: str = "local") -> Application:
        return self.update(app_id, learner_id=learner_id, status="withdrawn")

    def due(self, on_date: str, learner_id: str = "local") -> list[Application]:
        placeholders = ",".join("?" for _ in TERMINAL_STATUSES)
        sql = (
            "SELECT * FROM application "
            "WHERE learner_id = ? AND next_action_at IS NOT NULL "
            f"AND next_action_at <= ? AND status NOT IN ({placeholders}) "
            "ORDER BY next_action_at, company, id"
        )
        params = [learner_id, on_date, *sorted(TERMINAL_STATUSES)]
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_application(row) for row in rows]

    def counts(self, learner_id: str = "local") -> dict[str, int]:
        result = {status: 0 for status in STATUSES}
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) FROM application "
                "WHERE learner_id = ? GROUP BY status",
                (learner_id,),
            ).fetchall()
        for status, count in rows:
            result[status] = int(count)
        return result

    def _upsert(self, application: Application) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO application
                (id, learner_id, company, role, source, status, applied_at,
                 next_action_at, next_action, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  company=excluded.company,
                  role=excluded.role,
                  source=excluded.source,
                  status=excluded.status,
                  applied_at=excluded.applied_at,
                  next_action_at=excluded.next_action_at,
                  next_action=excluded.next_action,
                  notes=excluded.notes,
                  updated_at=excluded.updated_at
                """,
                (
                    application.id, application.learner_id,
                    application.company, application.role,
                    application.source, application.status,
                    application.applied_at, application.next_action_at,
                    application.next_action, application.notes,
                    application.created_at, application.updated_at,
                ),
            )

    @staticmethod
    def _row_to_application(row: sqlite3.Row) -> Application:
        return Application(
            id=row["id"], learner_id=row["learner_id"],
            company=row["company"], role=row["role"],
            source=row["source"], status=row["status"],
            applied_at=row["applied_at"], next_action_at=row["next_action_at"],
            next_action=row["next_action"], notes=row["notes"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )
