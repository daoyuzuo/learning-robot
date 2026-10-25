"""Draft state and files for the content studio.

The studio must stay independent of the learning engine, so it keeps its own
UTC helpers instead of importing ``testbridge.learning``.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from testbridge.studio.version import PROMPT_VERSION

SCHEMA = "studio/1"
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")
STEPS = ("outline", "research", "lessons", "validation", "promote", "batch")
SEARCH_BACKENDS = ("auto", "deepseek", "openalex")
MAX_MODULES = 3
MAX_LESSONS_PER_MODULE = 5
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


def _process_alive(pid: int) -> bool:
    """Return whether ``pid`` is a live process.

    Windows has no signal 0, so it asks the kernel for the exit code; POSIX
    uses the usual no-op signal. Unknown failures count as dead so a stale
    ``running`` step never blocks the UI forever.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [
            ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong,
        ]
        kernel32.GetExitCodeProcess.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong),
        ]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.OpenProcess(
            process_query_limited_information, False, pid
        )
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class DraftStore:
    def __init__(
        self,
        root: Path,
        *,
        instance_id: str | None = None,
        pid: int | None = None,
    ) -> None:
        self.root = root
        self.instance_id = instance_id or uuid.uuid4().hex
        self.pid = os.getpid() if pid is None else pid
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
        module_count: int = 1,
        lessons_per_module: int | None = None,
        lesson_count: int | None = None,
        searches_per_lesson: int,
        model: str,
        prompt_version: str = PROMPT_VERSION,
        search_backend: str = "auto",
    ) -> dict:
        if not ID_RE.fullmatch(draft_id):
            raise DraftError("invalid_id", "草稿 ID 只能包含字母、数字和连字符")
        if lessons_per_module is None:
            lessons_per_module = lesson_count or 1
        if lesson_count is None:
            lesson_count = module_count * lessons_per_module
        if not 1 <= module_count <= MAX_MODULES:
            raise DraftError("invalid_module_count", "模块数必须在 1–3 之间")
        if not 1 <= lessons_per_module <= MAX_LESSONS_PER_MODULE:
            raise DraftError(
                "invalid_lessons_per_module", "每模块课数必须在 1–5 之间"
            )
        if lesson_count != module_count * lessons_per_module:
            raise DraftError("invalid_lesson_count", "总课数与模块数不匹配")
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
            "module_count": module_count,
            "lessons_per_module": lessons_per_module,
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
                "batch": {
                    "status": "pending", "error": None, "at": None,
                    "mode": None, "done": 0, "total": 0,
                },
            },
        }
        self.path(draft_id).mkdir(parents=True, exist_ok=True)
        self.save(draft)
        return draft

    def load(self, draft_id: str) -> dict:
        # Serialize reads with writes: Windows rejects replacing a file that
        # another thread is reading, and batch jobs write while the UI polls.
        with self._lock:
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
        with self._lock:
            if not self.root.is_dir():
                return []
            drafts = []
            for item in sorted(self.root.iterdir()):
                if (item / "draft.json").is_file():
                    drafts.append(json.loads(
                        (item / "draft.json").read_text(encoding="utf-8")
                    ))
            return sorted(drafts, key=lambda draft: draft["id"])

    def update(self, draft_id: str, mutator: Callable[[dict], Any]) -> Any:
        """Load, mutate and save a draft while holding the store lock.

        Mutators must re-check any state they depend on: the lock makes the
        check and the following write one atomic step.
        """
        with self._lock:
            draft = self.load(draft_id)
            result = mutator(draft)
            self.save(draft)
            return result

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
            container = draft["steps"].setdefault(step, {})
            if lesson_id is not None:
                entry = container.setdefault(lesson_id, _step())
            else:
                entry = container
            if status is not None:
                entry["status"] = status
                entry["at"] = _iso(_utcnow())
                if status == "running":
                    entry["owner"] = self.instance_id
                    entry["pid"] = self.pid
                else:
                    entry.pop("owner", None)
                    entry.pop("pid", None)
            entry["error"] = error
            if extra:
                entry.update(extra)
            self.save(draft)
            return draft

    def _owned_by_live_process(self, entry: dict) -> bool:
        """Whether another live server owns this running step.

        Two servers may share ``drafts/`` during development. Startup must not
        mark the other server's jobs as interrupted, but a step left behind by
        a crashed process (or by an earlier store instance in this process)
        still needs to be released.
        """
        owner = entry.get("owner")
        pid = entry.get("pid")
        if not owner or owner == self.instance_id:
            return False
        if not isinstance(pid, int) or pid == self.pid:
            return False
        return _process_alive(pid)

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
                    if entry.get("status") != "running":
                        continue
                    if self._owned_by_live_process(entry):
                        continue
                    entry["status"] = "failed"
                    entry["error"] = "interrupted"
                    entry.pop("owner", None)
                    entry.pop("pid", None)
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
