"""Committable learning-state snapshots (evidence + goal + target JD)."""

import json
from pathlib import Path

from testbridge.career.store import TargetJd, TargetJdStore
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.learning.store import Goal, LearningStore
from testbridge.sync import (
    EVIDENCE_FILE,
    GOAL_FILE,
    MANIFEST_FILE,
    TARGET_FILE,
    export_state,
    import_state,
    resolve_state_dir,
    sync_state,
)


def event(kind: str = "exercise_attempt", **kwargs):
    return new_event(kind=kind, concept_ids=["c-one"], **kwargs)


def test_resolve_state_dir_defaults_next_to_the_database(tmp_path: Path) -> None:
    assert resolve_state_dir(tmp_path / "e.db") == tmp_path / "state"


def test_resolve_state_dir_honours_override_and_off_switch(tmp_path: Path) -> None:
    assert resolve_state_dir(tmp_path / "e.db", "elsewhere") == Path("elsewhere")
    assert resolve_state_dir(tmp_path / "e.db", "0") is None
    assert (
        resolve_state_dir(
            tmp_path / "e.db", environ={"TESTBRIDGE_STATE_DIR": "env-dir"}
        )
        == Path("env-dir")
    )
    assert (
        resolve_state_dir(
            tmp_path / "e.db", "explicit", environ={"TESTBRIDGE_STATE_DIR": "0"}
        )
        == Path("explicit")
    )


def test_export_then_import_restores_evidence(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    store = EvidenceStore(source)
    first = event(lesson_id="L-ONE", exercise_id="EX-ONE", outcome="correct", score=1.0,
                  max_score=1.0)
    second = event(kind="self_assess", outcome="submitted")
    store.append(first)
    store.append(second)

    state_dir = tmp_path / "state"
    report = export_state(source, state_dir)
    assert report.total == 2
    assert report.changed is True
    assert (state_dir / EVIDENCE_FILE).is_file()

    target = tmp_path / "target.db"
    merged = import_state(target, state_dir)
    assert merged.imported == 2
    restored = EvidenceStore(target).list()
    assert {item.id for item in restored} == {first.id, second.id}


def test_export_is_sorted_and_stable(tmp_path: Path) -> None:
    db = tmp_path / "e.db"
    store = EvidenceStore(db)
    late = event()
    early = event()
    store.append(late)
    store.append(early)
    state_dir = tmp_path / "state"
    export_state(db, state_dir)
    lines = (state_dir / EVIDENCE_FILE).read_text(encoding="utf-8").splitlines()
    keys = [
        (json.loads(line)["created_at"], json.loads(line)["id"]) for line in lines
    ]
    assert keys == sorted(keys)

    before = (state_dir / EVIDENCE_FILE).read_text(encoding="utf-8")
    assert export_state(db, state_dir).changed is False
    assert (state_dir / EVIDENCE_FILE).read_text(encoding="utf-8") == before


def test_two_databases_merge_into_union_without_duplicates(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    one = tmp_path / "one.db"
    two = tmp_path / "two.db"
    EvidenceStore(one).append(event(lesson_id="L-ONE"))
    EvidenceStore(two).append(event(lesson_id="L-TWO"))

    export_state(one, state_dir)
    export_state(two, state_dir)  # second machine appends its own event

    merged = tmp_path / "merged.db"
    report = import_state(merged, state_dir)
    assert report.imported == 2
    assert EvidenceStore(merged).count() == 2

    again = import_state(merged, state_dir)
    assert again.imported == 0
    assert EvidenceStore(merged).count() == 2


def test_import_skips_dirty_lines_with_warnings(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    good = event()
    (state_dir / EVIDENCE_FILE).write_text(
        "\n".join(
            [
                json.dumps({"id": "bad", "learner_id": "local", "kind": "x"}),
                json.dumps({"id": good.id}),  # missing required fields
                json.dumps(_as_dict(good)),
                "{not json",
                "",
            ]
        ),
        encoding="utf-8",
    )
    warnings: list[str] = []
    report = import_state(tmp_path / "e.db", state_dir, on_warning=warnings.append)
    assert report.imported == 1
    assert len(warnings) == 3


def _as_dict(event_obj) -> dict:
    from dataclasses import asdict

    return asdict(event_obj)


def test_goal_round_trip_keeps_snapshot_timestamp(tmp_path: Path) -> None:
    db = tmp_path / "e.db"
    LearningStore(db).set_goal(Goal(target_role="测试开发", daily_minutes=60,
                                    concept_overrides={"c-one": 1.5}))
    state_dir = tmp_path / "state"
    export_state(db, state_dir)

    first = (state_dir / GOAL_FILE).read_text(encoding="utf-8")
    stamp = json.loads(first)["updated_at"]

    restored = tmp_path / "restored.db"
    assert import_state(restored, state_dir).goal_merged is True
    assert LearningStore(restored).get_goal().daily_minutes == 60
    assert LearningStore(restored).get_goal().concept_overrides == {"c-one": 1.5}
    assert LearningStore(restored).goal_updated_at() == stamp

    # Import + export must not rewrite the timestamp, otherwise every startup
    # would dirty the working tree.
    export_state(restored, state_dir)
    assert (state_dir / GOAL_FILE).read_text(encoding="utf-8") == first


def test_newer_local_goal_wins_over_older_snapshot(tmp_path: Path) -> None:
    db = tmp_path / "e.db"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / GOAL_FILE).write_text(
        json.dumps(
            {
                "learner_id": "local",
                "target_role": "old",
                "weekly_hours": 0.0,
                "daily_minutes": 10,
                "concept_overrides": {},
                "updated_at": "2020-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    LearningStore(db).set_goal(Goal(target_role="new", daily_minutes=90))

    assert import_state(db, state_dir).goal_merged is False
    assert LearningStore(db).get_goal().daily_minutes == 90
    assert LearningStore(db).get_goal().target_role == "new"


def test_target_jd_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "e.db"
    TargetJdStore(db).save(
        TargetJd(
            learner_id="local",
            source_text="招聘时间同步测试工程师",
            target_role="测试开发",
            requirements=[{"text": "时间同步", "concepts": ["c-one"]}],
            weights={"c-one": 1.5},
            model="fake",
        )
    )
    state_dir = tmp_path / "state"
    export_state(db, state_dir)
    assert (state_dir / TARGET_FILE).is_file()

    restored = tmp_path / "restored.db"
    assert import_state(restored, state_dir).target_merged is True
    saved = TargetJdStore(restored).get()
    assert saved is not None
    assert saved.weights == {"c-one": 1.5}
    assert saved.requirements[0]["text"] == "时间同步"


def test_manifest_counts_events_and_learners(tmp_path: Path) -> None:
    db = tmp_path / "e.db"
    store = EvidenceStore(db)
    store.append(event())
    store.append(new_event(kind="interview", concept_ids=["c-one"], learner_id="other"))
    state_dir = tmp_path / "state"
    export_state(db, state_dir)
    manifest = json.loads((state_dir / MANIFEST_FILE).read_text(encoding="utf-8"))
    assert manifest["schema"] == 1
    assert manifest["events"] == 2
    assert manifest["learners"] == ["local", "other"]


def test_sync_state_reports_import_and_export(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    EvidenceStore(source).append(event())
    state_dir = tmp_path / "state"
    export_state(source, state_dir)

    target = tmp_path / "target.db"
    report = sync_state(target, state_dir)
    assert report.imported == 1
    assert report.total == 1
    assert EvidenceStore(target).count() == 1


def test_disabled_state_dir_is_a_no_op(tmp_path: Path) -> None:
    report = export_state(tmp_path / "e.db", None)
    assert report.changed is False
    assert not (tmp_path / "state").exists()
    assert import_state(tmp_path / "e.db", None).imported == 0