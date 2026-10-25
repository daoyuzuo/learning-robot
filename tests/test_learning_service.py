from datetime import datetime, timezone
from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.learning.service import LearningService
from testbridge.learning.store import LearningStore

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def service(tmp_path: Path) -> LearningService:
    pack = load_pack(SAMPLE)
    return LearningService(
        pack, EvidenceStore(tmp_path / "e.db"), LearningStore(tmp_path / "l.db"),
        now_fn=lambda: NOW,
    )


def event(outcome: str) -> object:
    return new_event(
        kind="exercise_attempt", lesson_id="L-SYNC-001", exercise_id="EX-SYNC-001",
        concept_ids=["sensor-time-sync"], outcome=outcome,
        score=1.0 if outcome == "correct" else 0.0, max_score=1.0,
    )


def test_record_updates_mastery_and_review(tmp_path: Path) -> None:
    svc = service(tmp_path)
    item = event("correct")
    svc.evidence.append(item)
    svc.record(item)
    view = svc.mastery("sensor-time-sync")
    assert view.exercise_observations == 1
    assert view.estimate > 0
    assert svc.store.get_review("local", "EX-SYNC-001") is not None


def test_handoff_after_three_exercises(tmp_path: Path) -> None:
    svc = service(tmp_path)
    for _ in range(3):
        item = event("correct")
        svc.evidence.append(item)
        svc.record(item)
    view = svc.mastery("sensor-time-sync")
    assert view.exercise_observations == 3
    assert view.estimate == view.bkt_p


def test_self_assess_updates_rule_not_review(tmp_path: Path) -> None:
    svc = service(tmp_path)
    item = new_event(
        kind="self_assess", concept_ids=["sensor-time-sync"], outcome="submitted",
        score=0.5, max_score=1.0,
    )
    svc.evidence.append(item)
    svc.record(item)
    view = svc.mastery("sensor-time-sync")
    assert view.other_observations == 1
    assert svc.store.list_reviews("local") == {}
