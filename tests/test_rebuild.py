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
         value.other_observations, value.estimate, value.confidence, value.level)
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


def test_other_learner_events_are_ignored(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.evidence.append(replace(attempt("correct"), learner_id="other"))
    result = rebuild_state(service)
    assert result.events == 0
    assert service.store.list_mastery("local") == {}
    assert service.store.list_reviews("local") == {}


def test_unknown_concept_and_exercise_are_skipped(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    item = replace(
        new_event(
            kind="exercise_attempt", lesson_id="L-SYNC-001",
            exercise_id="EX-NOPE", concept_ids=["unknown"], outcome="correct",
            score=1.0, max_score=1.0,
        ),
        created_at=NOW.isoformat(),
    )
    service.evidence.append(item)
    result = rebuild_state(service)
    assert result.skipped_concepts == ["unknown"]
    assert result.skipped_exercises == ["EX-NOPE"]
    assert service.store.list_mastery("local") == {}
    assert service.store.list_reviews("local") == {}


def test_rebuild_skips_invalid_evidence_and_warns(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    good = replace(attempt("correct"), id="good")
    bad_time = replace(attempt("correct"), id="bad-time", created_at="yesterday")
    bad_score = replace(attempt("correct"), id="bad-score", score="abc")
    service.evidence.append(good)
    service.evidence.append(bad_time)
    service.evidence.append(bad_score)

    result = rebuild_state(service)

    assert result.events == 1
    assert len(result.warnings) == 2
    assert any("bad-time" in message for message in result.warnings)
    assert any("bad-score" in message for message in result.warnings)
    state = service.store.get_mastery("local", "sensor-time-sync")
    assert state is not None
    assert state.exercise_observations == 1


def test_duplicate_concept_ids_count_once(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    item = replace(
        attempt("correct"),
        concept_ids=["sensor-time-sync", "sensor-time-sync"],
    )
    service.evidence.append(item)
    rebuild_state(service)
    state = service.store.get_mastery("local", "sensor-time-sync")
    assert state is not None
    assert state.exercise_observations == 1
