from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.learning.rebuild import rebuild_state
from testbridge.learning.service import LearningService
from testbridge.learning.store import LearningStore

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def make_service(tmp_path: Path) -> LearningService:
    return LearningService(
        load_pack(SAMPLE), EvidenceStore(tmp_path / "e.db"),
        LearningStore(tmp_path / "l.db"), now_fn=lambda: NOW,
    )


def attempt(outcome: str, exercise_id: str = "EX-SYNC-001") -> object:
    item = new_event(
        kind="exercise_attempt", lesson_id="L-SYNC-001", exercise_id=exercise_id,
        concept_ids=["sensor-time-sync"], outcome=outcome,
        score=1.0 if outcome == "correct" else 0.0, max_score=1.0,
    )
    return replace(item, created_at=NOW.isoformat())


def comparable(service: LearningService) -> tuple:
    mastery = service.store.list_mastery("local")
    reviews = service.store.list_reviews("local")
    m = tuple(sorted(
        (key, value.rule_score, value.bkt_p, value.exercise_observations,
         value.other_observations, value.estimate, value.level)
        for key, value in mastery.items()
    ))
    r = tuple(sorted(
        (key, value.due, value.stability, value.difficulty, value.reps,
         value.lapses, value.state)
        for key, value in reviews.items()
    ))
    return m, r


def test_incremental_matches_rebuild(tmp_path: Path) -> None:
    items = [attempt(outcome) for outcome in ["correct", "incorrect", "correct"]]

    incremental = make_service(tmp_path / "a")
    for item in items:
        incremental.evidence.append(item)
        incremental.record(item)

    rebuilt = make_service(tmp_path / "b")
    for item in items:
        rebuilt.evidence.append(item)
    rebuild_state(rebuilt)
    assert comparable(incremental) == comparable(rebuilt)


def test_rebuild_is_idempotent(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.evidence.append(attempt("correct"))
    first = rebuild_state(service)
    snapshot = comparable(service)
    second = rebuild_state(service)
    assert first == second
    assert comparable(service) == snapshot


def test_superseded_events_are_skipped(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    old = attempt("correct")
    correction = replace(attempt("incorrect"), supersedes=old.id)
    service.evidence.append(old)
    service.evidence.append(correction)
    rebuild_state(service)
    view = service.mastery("sensor-time-sync")
    assert view.estimate < 0.5
