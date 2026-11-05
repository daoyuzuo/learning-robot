"""Mirror learning state into a committable, merge-friendly directory.

The SQLite database is the live store, but it is binary and ignored by git. A
learner who moves to another machine therefore loses every answer. This module
keeps a plain-text mirror under ``data/state/``:

- ``evidence.jsonl`` -- one evidence event per line, ascending by
  ``(created_at, id)`` so both machines append to the end and git merges them;
- ``goal.json`` / ``target-jd.json`` -- the learner's personal settings;
- ``manifest.json`` -- counts derived from the content above.

Evidence is the only source of truth: importing replays it through the normal
rebuild path, so mastery and review state are never copied from the snapshot.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from testbridge.career.jd import safe_text
from testbridge.career.store import TargetJd, TargetJdStore
from testbridge.evidence.store import EvidenceEvent, EvidenceStore, event_problem
from testbridge.learning.store import Goal, LearningStore
from testbridge.learning.timeutil import parse_iso

SCHEMA = 1
EVIDENCE_FILE = "evidence.jsonl"
GOAL_FILE = "goal.json"
TARGET_FILE = "target-jd.json"
MANIFEST_FILE = "manifest.json"
DISABLED_VALUES = {"0", "off", "false", "no", "disable", "disabled"}


@dataclass(frozen=True)
class SyncReport:
    """What a sync or export actually changed."""

    state_dir: Path
    imported: int = 0
    total: int = 0
    goal_merged: bool = False
    target_merged: bool = False
    changed: bool = False
    warnings: list[str] = field(default_factory=list)


def resolve_state_dir(
    db_path: Path,
    override: str | Path | None = None,
    environ: dict[str, str] | None = None,
) -> Path | None:
    """Where the snapshot lives for this database, or ``None`` when disabled.

    The default is ``<db parent>/state`` so a throwaway database (tests, CLI
    experiments) never touches the repository snapshot. ``TESTBRIDGE_STATE_DIR``
    can point elsewhere, and an explicit off switch preserves the old
    database-only behaviour.
    """
    env = os.environ if environ is None else environ
    raw: str | Path | None = override
    if raw is None:
        raw = env.get("TESTBRIDGE_STATE_DIR", "").strip() or None
    if raw is None:
        return db_path.parent / "state"
    text = str(raw).strip()
    if text.lower() in DISABLED_VALUES:
        return None
    return Path(text)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_text(path: Path, text: str) -> bool:
    """Atomically write ``text``; return whether the file content changed."""
    try:
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.part")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temporary, path)
    return True


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _evidence_line(event: EvidenceEvent) -> str:
    return json.dumps(asdict(event), ensure_ascii=False, sort_keys=True)


def _sort_key(event: EvidenceEvent) -> tuple[str, str]:
    return (event.created_at, event.id)


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #


def _import_evidence(
    store: EvidenceStore,
    state_dir: Path,
    warnings: list[str],
) -> int:
    path = state_dir / EVIDENCE_FILE
    if not path.is_file():
        return 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        warnings.append(f"{EVIDENCE_FILE}: cannot read: {exc}")
        return 0

    inserted = 0
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            warnings.append(f"{EVIDENCE_FILE} line {number}: invalid JSON: {exc.msg}")
            continue
        problem = event_problem(data)
        if problem:
            warnings.append(f"{EVIDENCE_FILE} line {number}: {problem}")
            continue
        try:
            event = EvidenceEvent(**data)
        except TypeError as exc:
            warnings.append(f"{EVIDENCE_FILE} line {number}: {exc}")
            continue
        if store._insert(event):
            inserted += 1
    return inserted


def _import_goal(store: LearningStore, state_dir: Path, warnings: list[str]) -> bool:
    data = _read_json(state_dir / GOAL_FILE)
    if data is None:
        if (state_dir / GOAL_FILE).is_file():
            warnings.append(f"{GOAL_FILE}: not a JSON object")
        return False
    learner_id = str(data.get("learner_id") or "local")
    updated_at = data.get("updated_at")
    if not isinstance(updated_at, str):
        warnings.append(f"{GOAL_FILE}: missing updated_at")
        return False
    try:
        parse_iso(updated_at)
    except (TypeError, ValueError):
        warnings.append(f"{GOAL_FILE}: created_at is not an ISO datetime")
        return False

    current = store.goal_updated_at(learner_id)
    if current is not None and _newer(current, updated_at):
        # The local settings were edited after the snapshot; keep them.
        return False

    overrides = data.get("concept_overrides")
    if not isinstance(overrides, dict):
        overrides = {}
    cleaned: dict[str, float] = {}
    for key, value in overrides.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            warnings.append(f"{GOAL_FILE}: dropped non-numeric override {key!r}")
            continue
        cleaned[str(key)] = float(value)

    def number(name: str, fallback: float) -> float:
        value = data.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return fallback
        return float(value)

    store.set_goal(
        Goal(
            learner_id=learner_id,
            target_role=str(data.get("target_role") or ""),
            weekly_hours=number("weekly_hours", 0.0),
            daily_minutes=int(number("daily_minutes", 45)),
            concept_overrides=cleaned,
        ),
        updated_at=updated_at,
    )
    return True


def _import_target(store: TargetJdStore, state_dir: Path, warnings: list[str]) -> bool:
    data = _read_json(state_dir / TARGET_FILE)
    if data is None:
        if (state_dir / TARGET_FILE).is_file():
            warnings.append(f"{TARGET_FILE}: not a JSON object")
        return False
    learner_id = str(data.get("learner_id") or "local")
    updated_at = data.get("updated_at")
    if not isinstance(updated_at, str):
        warnings.append(f"{TARGET_FILE}: missing updated_at")
        return False
    try:
        parse_iso(updated_at)
    except (TypeError, ValueError):
        warnings.append(f"{TARGET_FILE}: updated_at is not an ISO datetime")
        return False

    current = store.updated_at(learner_id)
    if current is not None and _newer(current, updated_at):
        return False

    source_text = safe_text(str(data.get("source_text") or ""))
    if not source_text:
        warnings.append(f"{TARGET_FILE}: empty source_text")
        return False
    requirements = data.get("requirements")
    if not isinstance(requirements, list):
        requirements = []
    weights: dict[str, float] = {}
    raw_weights = data.get("weights")
    if isinstance(raw_weights, dict):
        for key, value in raw_weights.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                warnings.append(f"{TARGET_FILE}: dropped non-numeric weight {key!r}")
                continue
            weights[str(key)] = float(value)

    store.save(
        TargetJd(
            learner_id=learner_id,
            source_text=source_text,
            target_role=safe_text(str(data.get("target_role") or "")),
            requirements=[item for item in requirements if isinstance(item, dict)],
            weights=weights,
            model=data.get("model") if isinstance(data.get("model"), str) else None,
        ),
        updated_at=updated_at,
    )
    return True


def _newer(left: str, right: str) -> bool:
    """True when ``left`` is strictly after ``right`` (invalid values compare low)."""
    try:
        return parse_iso(left) > parse_iso(right)
    except (TypeError, ValueError):
        return False


def import_state(
    db_path: Path,
    state_dir: Path | None,
    *,
    on_warning: Callable[[str], None] | None = None,
) -> SyncReport:
    """Merge a snapshot into the database, never overwriting newer local settings."""
    if state_dir is None:
        return SyncReport(state_dir=Path("."), warnings=[])
    warnings: list[str] = []
    evidence = EvidenceStore(db_path)
    learning = LearningStore(db_path)
    targets = TargetJdStore(db_path)

    imported = _import_evidence(evidence, state_dir, warnings)
    goal_merged = _import_goal(learning, state_dir, warnings)
    target_merged = _import_target(targets, state_dir, warnings)

    for message in warnings:
        if on_warning is not None:
            on_warning(message)
    return SyncReport(
        state_dir=state_dir,
        imported=imported,
        total=evidence.count(),
        goal_merged=goal_merged,
        target_merged=target_merged,
        warnings=warnings,
    )


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #


def export_state(
    db_path: Path,
    state_dir: Path | None,
    learner_id: str = "local",
) -> SyncReport:
    """Write the current database state into the snapshot directory."""
    if state_dir is None:
        return SyncReport(state_dir=Path("."), warnings=[])
    evidence = EvidenceStore(db_path)
    learning = LearningStore(db_path)
    targets = TargetJdStore(db_path)

    merged: dict[str, EvidenceEvent] = {}
    # The snapshot first so a machine that has not seen the latest commit still
    # keeps events it imported earlier; the database then wins by id.
    path = state_dir / EVIDENCE_FILE
    if path.is_file():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                data = json.loads(line)
                if event_problem(data):
                    continue
                event = EvidenceEvent(**data)
                merged[event.id] = event
        except (OSError, ValueError, TypeError):
            pass
    for event in evidence.list(limit=1_000_000):
        merged[event.id] = event

    events = sorted(merged.values(), key=_sort_key)
    state_dir.mkdir(parents=True, exist_ok=True)
    changed = _write_text(
        state_dir / EVIDENCE_FILE,
        "".join(_evidence_line(event) + "\n" for event in events),
    )
    changed |= _export_goal(learning, state_dir, learner_id)
    changed |= _export_target(targets, state_dir, learner_id)
    changed |= _write_text(
        state_dir / MANIFEST_FILE,
        _json_text(
            {
                "schema": SCHEMA,
                "events": len(events),
                "learners": sorted({event.learner_id for event in events}),
                "last_event_at": events[-1].created_at if events else None,
            }
        ),
    )
    return SyncReport(state_dir=state_dir, total=len(events), changed=changed)


def _export_goal(store: LearningStore, state_dir: Path, learner_id: str) -> bool:
    updated_at = store.goal_updated_at(learner_id)
    if updated_at is None:
        return False
    goal = store.get_goal(learner_id)
    return _write_text(
        state_dir / GOAL_FILE,
        _json_text(
            {
                "learner_id": goal.learner_id,
                "target_role": goal.target_role,
                "weekly_hours": goal.weekly_hours,
                "daily_minutes": goal.daily_minutes,
                "concept_overrides": goal.concept_overrides,
                "updated_at": updated_at,
            }
        ),
    )


def _export_target(store: TargetJdStore, state_dir: Path, learner_id: str) -> bool:
    target = store.get(learner_id)
    if target is None:
        return False
    return _write_text(
        state_dir / TARGET_FILE,
        _json_text(
            {
                "learner_id": target.learner_id,
                "source_text": target.source_text,
                "target_role": target.target_role,
                "requirements": target.requirements,
                "weights": target.weights,
                "model": target.model,
                "updated_at": target.updated_at,
            }
        ),
    )


def sync_state(
    db_path: Path,
    state_dir: Path | None,
    learner_id: str = "local",
    *,
    on_warning: Callable[[str], None] | None = None,
) -> SyncReport:
    """Import the snapshot, then export the union back."""
    imported = import_state(db_path, state_dir, on_warning=on_warning)
    exported = export_state(db_path, state_dir, learner_id)
    return SyncReport(
        state_dir=exported.state_dir,
        imported=imported.imported,
        total=exported.total,
        goal_merged=imported.goal_merged,
        target_merged=imported.target_merged,
        changed=exported.changed,
        warnings=imported.warnings,
    )


def package_all(
    db_path: Path,
    state_dir: Path | None,
    pack_path: Path,
    learner_id: str = "local",
    *,
    on_warning: Callable[[str], None] | None = None,
) -> SyncReport:
    """Sync, then rebuild derived mastery/review state from the merged evidence."""
    from testbridge.content.repository import load_pack
    from testbridge.learning.rebuild import rebuild_state
    from testbridge.learning.service import LearningService

    report = sync_state(db_path, state_dir, learner_id, on_warning=on_warning)
    pack = load_pack(pack_path)
    service = LearningService(pack, EvidenceStore(db_path), LearningStore(db_path), learner_id)
    rebuild_state(service)
    return report