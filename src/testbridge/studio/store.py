"""Draft state and files for the content studio.

The studio must stay independent of the learning engine, so it keeps its own
UTC helpers instead of importing ``testbridge.learning``.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "studio/1"
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")
STEPS = ("outline", "research", "lessons", "validation", "promote")
SEARCH_BACKENDS = ("auto", "deepseek", "openalex")
MIN_LESSONS = 1
MAX_LESSONS = 5
MIN_SEARCHES = 1
MAX_SEARCHES = 50


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


class DraftError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class DraftNotFound(DraftError):
    def __init__(self, draft_id: str) -> None:
        super().__init__("draft_not_found", f"草稿不存在：{draft_id}")


def _step() -> dict:
    return {"status": "pending", "error": None, "at": None}


class DraftStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = threading.RLock()

    def path(self, draft_id: str) -> Path:
        return self.root / draft_id

    def exists(self, draft_id: str) -> bool:
        return (self.path(draft_id) / "draft.json").is_file()

    def create(
        self,
        *,
        draft_id: str,
        topic: str,
        level: str,
        lesson_count: int,
        searches_per_lesson: int,
        model: str,
        prompt_version: str,
        search_backend: str = "auto",
    ) -> dict:
        if not ID_RE.fullmatch(draft_id):
            raise DraftError("invalid_id", "草稿 ID 只能包含字母、数字和连字符")
        if not MIN_LESSONS <= lesson_count <= MAX_LESSONS:
            raise DraftError("invalid_lesson_count", "课数必须在 1–5 之间")
        if not MIN_SEARCHES <= searches_per_lesson <= MAX_SEARCHES:
            raise DraftError("invalid_search_budget", "每课检索次数必须在 1–50 之间")
        if search_backend not in SEARCH_BACKENDS:
            raise DraftError(
                "invalid_search_backend",
                "检索源必须是 auto / deepseek / openalex",
            )
        if self.exists(draft_id):
            raise DraftError("draft_exists", f"草稿已存在：{draft_id}")
        now = _iso(_utcnow())
        draft = {
            "schema": SCHEMA,
            "id": draft_id,
            "topic": topic,
            "level": level,
            "lesson_count": lesson_count,
            "searches_per_lesson": searches_per_lesson,
            "model": model,
            "prompt_version": prompt_version,
            "search_backend": search_backend,
            "created_at": now,
            "updated_at": now,
            "usage": {"searches": 0, "llm_calls": 0},
            "steps": {
                "outline": _step(),
                "research": {},
                "lessons": {},
                "validation": _step(),
                "promote": _step(),
            },
        }
        self.path(draft_id).mkdir(parents=True, exist_ok=True)
        self.save(draft)
        return draft

    def load(self, draft_id: str) -> dict:
        target = self.path(draft_id) / "draft.json"
        if not target.is_file():
            raise DraftNotFound(draft_id)
        return json.loads(target.read_text(encoding="utf-8"))

    def save(self, draft: dict) -> None:
        with self._lock:
            draft["updated_at"] = _iso(_utcnow())
            target = self.path(draft["id"]) / "draft.json"
            temporary = target.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary.replace(target)

    def list(self) -> list[dict]:
        if not self.root.is_dir():
            return []
        drafts = []
        for item in sorted(self.root.iterdir()):
            if (item / "draft.json").is_file():
                drafts.append(json.loads(
                    (item / "draft.json").read_text(encoding="utf-8")
                ))
        return sorted(drafts, key=lambda draft: draft["id"])

    def set_step(
        self,
        draft_id: str,
        step: str,
        *,
        status: str | None = None,
        error: str | None = None,
        extra: dict | None = None,
        lesson_id: str | None = None,
    ) -> dict:
        with self._lock:
            draft = self.load(draft_id)
            container = draft["steps"][step]
            if lesson_id is not None:
                entry = container.setdefault(lesson_id, _step())
            else:
                entry = container
            if status is not None:
                entry["status"] = status
                entry["at"] = _iso(_utcnow())
            entry["error"] = error
            if extra:
                entry.update(extra)
            self.save(draft)
            return draft

    def mark_interrupted(self) -> int:
        changed = 0
        for draft in self.list():
            dirty = False
            for step in STEPS:
                container = draft["steps"].get(step)
                entries = (
                    [container] if isinstance(container, dict) and "status" in container
                    else list((container or {}).values())
                )
                for entry in entries:
                    if entry.get("status") == "running":
                        entry["status"] = "failed"
                        entry["error"] = "interrupted"
                        changed += 1
                        dirty = True
            if dirty:
                self.save(draft)
        return changed

    def write(self, draft_id: str, relative: str, text: str) -> Path:
        target = self.path(draft_id) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(target)
        return target

    def read(self, draft_id: str, relative: str) -> str:
        return (self.path(draft_id) / relative).read_text(encoding="utf-8")
