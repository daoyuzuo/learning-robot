"""Snapshots, metrics and comparisons for content evolution.

Snapshots keep the full lesson HTML plus the exercises and resources it
references, so a later run can show what changed between two generations.
Everything here is deterministic: no model calls and no learning-engine
imports.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from collections.abc import Callable, Iterable
from datetime import datetime, timezone

import yaml

from testbridge.contract.loader import load_lesson_file
from testbridge.contract.models import LEVEL_ORDER
from testbridge.quality.evaluate import QualityUnavailable, evaluate_draft
from testbridge.studio.jobs import JobBusy, JobRunner
from testbridge.studio.outline import LessonPlan
from testbridge.studio.store import ID_RE, DraftStore

SNAPSHOT_SCHEMA = "studio-snapshot/1"
EMPTY_METRICS: dict = {
    "exercise_count": 0, "types": [], "levels": [], "max_level": "",
    "resource_count": 0, "trust": {}, "html_hash": "",
}


def _empty_metrics() -> dict:
    """Return a fresh empty metric block.

    Callers may mutate the returned dict (for example after a failed rewrite);
    sharing one module-level object would leak that mutation into later
    snapshots.
    """
    return {
        "exercise_count": 0, "types": [], "levels": [], "max_level": "",
        "resource_count": 0, "trust": {}, "html_hash": "",
    }


def _yaml_list(
    store: DraftStore, draft_id: str, relative: str, key: str
) -> list[dict]:
    try:
        data = yaml.safe_load(store.read(draft_id, relative))
    except FileNotFoundError:
        return []
    if not isinstance(data, dict):
        return []
    items = data.get(key) or []
    return [item for item in items if isinstance(item, dict)]


def _read_lesson(
    store: DraftStore, draft_id: str, plan: LessonPlan
) -> tuple[str, list[dict], list[dict], dict]:
    path = (
        store.path(draft_id)
        / "modules" / plan.module_id / "lessons" / f"{plan.lesson_id}.html"
    )
    if not path.is_file():
        return "", [], [], _empty_metrics()

    html = path.read_text(encoding="utf-8")
    manifest, _ = load_lesson_file(path)
    exercises = [
        item
        for item in _yaml_list(store, draft_id, "exercises.yaml", "exercises")
        if item.get("id") in manifest.exercises
    ]
    resources = [
        item
        for item in _yaml_list(store, draft_id, "resources.yaml", "resources")
        if item.get("id") in manifest.resources
    ]

    levels = [str(item.get("level") or "") for item in exercises]
    types = sorted({
        str(item.get("type") or "") for item in exercises if item.get("type")
    })
    trust: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0}
    for item in resources:
        name = str(item.get("trust") or "?")
        trust[name] = trust.get(name, 0) + 1

    metrics = {
        "exercise_count": len(exercises),
        "types": types,
        "levels": levels,
        "max_level": max(
            levels, key=lambda value: LEVEL_ORDER.get(value, 0), default=""
        ),
        "resource_count": len(resources),
        "trust": trust,
        "html_hash": hashlib.sha256(html.encode("utf-8")).hexdigest()[:16],
    }
    return html, exercises, resources, metrics


def lesson_metrics(
    store: DraftStore, draft_id: str, plan: LessonPlan
) -> dict:
    """Return counts and hashes for one lesson without keeping its content."""
    return _read_lesson(store, draft_id, plan)[3]


def snapshot_lesson(
    store: DraftStore, draft_id: str, plan: LessonPlan
) -> dict:
    """Build a full snapshot of one lesson's current content."""
    html, exercises, resources, metrics = _read_lesson(store, draft_id, plan)
    draft = store.load(draft_id)
    entry = draft.get("steps", {}).get("lessons", {}).get(plan.lesson_id) or {}
    version = (
        entry.get("prompt_version")
        or draft.get("prompt_version")
        or "studio/1"
    )
    return {
        "schema": SNAPSHOT_SCHEMA,
        "draft_id": draft_id,
        "lesson_id": plan.lesson_id,
        "module_id": plan.module_id,
        "lesson_title": plan.title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt_version": version,
        "html": html,
        "exercises": exercises,
        "resources": resources,
        "metrics": metrics,
    }


def timestamp_now() -> str:
    """Return the Windows-safe UTC timestamp used in history filenames."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _stamp(created_at: str) -> str:
    if not isinstance(created_at, str):
        raise TypeError(f"created_at 必须是字符串：{created_at!r}")
    text = (
        created_at[:-1] + "+00:00"
        if created_at.endswith("Z")
        else created_at
    )
    try:
        value = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"created_at 不是合法时间：{created_at!r}") from exc
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def save_snapshot(store: DraftStore, snapshot: dict) -> str:
    """Write a snapshot atomically under ``history/<lesson>/``.

    Returns the path relative to the draft directory.
    """
    draft_id = str(snapshot["draft_id"])
    lesson_id = str(snapshot["lesson_id"])
    if not ID_RE.fullmatch(draft_id):
        raise ValueError(f"草稿 ID 不合法：{draft_id}")
    if not ID_RE.fullmatch(lesson_id):
        raise ValueError(f"课程 ID 不合法：{lesson_id}")
    relative = f"history/{lesson_id}/{_stamp(snapshot['created_at'])}.json"
    store.write(
        draft_id, relative,
        # Hand-edited YAML may load unquoted dates as ``datetime.date``.
        json.dumps(snapshot, ensure_ascii=False, indent=2, default=str),
    )
    return relative


def latest_snapshot(
    store: DraftStore, draft_id: str, lesson_id: str
) -> dict | None:
    """Return the newest snapshot for a lesson, or ``None`` if none exist."""
    if not ID_RE.fullmatch(str(draft_id)) or not ID_RE.fullmatch(
        str(lesson_id)
    ):
        return None
    root = store.path(draft_id) / "history" / lesson_id
    if not root.is_dir():
        return None
    files = sorted(root.glob("*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def compare_snapshots(before: dict, after: dict) -> dict:
    """Summarize the differences between two snapshots."""
    old = before.get("metrics") or EMPTY_METRICS
    new = after.get("metrics") or EMPTY_METRICS
    old_types = set(old.get("types") or [])
    new_types = set(new.get("types") or [])
    return {
        "html": old.get("html_hash") != new.get("html_hash"),
        "exercise_count": (
            new.get("exercise_count", 0) - old.get("exercise_count", 0)
        ),
        "types_added": sorted(new_types - old_types),
        "types_removed": sorted(old_types - new_types),
        "max_level_before": old.get("max_level", ""),
        "max_level_after": new.get("max_level", ""),
        "resource_count": (
            new.get("resource_count", 0) - old.get("resource_count", 0)
        ),
        "prompt_version": (
            before.get("prompt_version") != after.get("prompt_version")
        ),
    }


def draft_quality(store: DraftStore, draft_id: str) -> dict | None:
    """Return the pack quality summary, or ``None`` when the pack is invalid."""
    draft = store.load(draft_id)
    try:
        report = evaluate_draft(
            store.path(draft_id),
            research_dir=store.path(draft_id) / "research",
            budget=int(draft.get("searches_per_lesson") or 1),
        )
    except QualityUnavailable:
        return None
    return {"score": report.score, "possible": report.possible, "ok": report.ok}


class EvolutionBusy(Exception):
    """An evolution job is already running."""


def _valid_report(result: object) -> bool:
    """Return whether a callback report has the expected shape."""
    if not isinstance(result, dict):
        return False
    lessons = result.get("lessons")
    return isinstance(lessons, list) and all(
        isinstance(item, dict) for item in lessons
    )


class EvolutionJob:
    """Process several drafts under their batch locks and track progress.

    The callback owns per-draft work (snapshots, rewrites, reports). This class
    only sequences drafts, remembers the in-memory progress the UI polls, and
    keeps a busy or failing draft from stopping the remaining ones.
    """

    def __init__(self, store: DraftStore, runner: JobRunner) -> None:
        self.store = store
        self.runner = runner
        self._lock = threading.Lock()
        self._state: dict = {
            "status": "idle", "total": 0, "done": 0,
            "current": None, "results": [], "error": None,
        }

    def start(
        self,
        groups: Iterable[tuple[str, list[str]]],
        process_draft: Callable[[str, list[str]], dict],
        inline: bool = False,
    ) -> None:
        """Process ``(draft_id, lesson_ids)`` groups in order."""
        groups = [(draft_id, list(lessons)) for draft_id, lessons in groups]
        with self._lock:
            if self._state["status"] == "running":
                raise EvolutionBusy("evolution is already running")
            total = sum(len(lessons) for _, lessons in groups)
            self._state = {
                "status": "running", "total": total, "done": 0,
                "current": None, "results": [], "error": None,
            }

        def run() -> None:
            failures = 0
            try:
                for draft_id, lessons in groups:
                    with self._lock:
                        self._state["current"] = {
                            "draft_id": draft_id, "lesson_id": None,
                        }
                    try:
                        result = self.runner.run_batch_now(
                            draft_id,
                            lambda draft_id=draft_id, lessons=lessons: (
                                process_draft(draft_id, lessons)
                            ),
                        )
                    except JobBusy:
                        result = {
                            "draft_id": draft_id,
                            "error": "草稿正在执行其他任务",
                            "lessons": [],
                        }
                    except Exception as exc:  # noqa: BLE001 - continue
                        result = {
                            "draft_id": draft_id,
                            "error": str(exc),
                            "lessons": [],
                        }
                    if not _valid_report(result):
                        result = {
                            "draft_id": draft_id,
                            "error": "草稿结果格式无效",
                            "lessons": [],
                        }
                    with self._lock:
                        self._state["results"].append(result)
                        self._state["done"] += len(result["lessons"])
                        self._state["current"] = None
                    if result.get("error") or any(
                        not item.get("ok") for item in result["lessons"]
                    ):
                        failures += 1
            except Exception as exc:  # noqa: BLE001 - never stay running
                with self._lock:
                    if self._state["status"] == "running":
                        self._state["status"] = "failed"
                        self._state["error"] = str(exc)
                    self._state["current"] = None
            else:
                with self._lock:
                    self._state["status"] = "failed" if failures else "done"
                    self._state["error"] = (
                        f"{failures} 个草稿失败" if failures else None
                    )

        if inline:
            run()
        else:
            threading.Thread(target=run, daemon=True).start()

    def status(self) -> dict:
        """Return a copy of the in-memory job state."""
        with self._lock:
            return copy.deepcopy(self._state)
