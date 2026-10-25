"""Lesson snapshots, metrics and before/after comparisons."""

from __future__ import annotations

import json
import threading
import time
from datetime import date
from pathlib import Path

import pytest
import yaml

from testbridge.studio.evolution import (
    EvolutionBusy,
    EvolutionJob,
    compare_snapshots,
    draft_quality,
    latest_snapshot,
    lesson_metrics,
    save_snapshot,
    snapshot_lesson,
)
from testbridge.studio.jobs import JobRunner
from testbridge.studio.outline import LessonPlan
from testbridge.studio.store import DraftStore


def single_choice() -> dict:
    return {
        "id": "EX-1", "type": "single_choice", "concepts": ["c-one"],
        "level": "L2", "prompt": "选一个",
        "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        "answer": "a",
    }


def multi_choice() -> dict:
    return {
        "id": "EX-2", "type": "multi_choice", "concepts": ["c-one"],
        "level": "L2", "prompt": "多选",
        "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        "answer": ["a"],
    }


def resource() -> dict:
    return {
        "id": "DOC-1", "title": "官方文档", "url": "https://docs.example/x",
        "type": "official-doc", "trust": "A", "license": "Apache-2.0",
        "last_verified": "2026-10-25", "coverage": ["c-one"], "why": "官方",
    }


def setup_lesson(
    tmp_path: Path,
    *,
    exercises: list[dict] | None = None,
    prompt_version: str = "studio/2",
) -> tuple[DraftStore, LessonPlan]:
    exercises = exercises if exercises is not None else [single_choice()]
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id="demo", topic="ROS 2 执行器", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m",
    )
    store.write("demo", "pack.yaml", yaml.safe_dump({
        "schema": "tb/1", "id": "demo", "version": "0.1.0", "title": "演示",
    }, allow_unicode=True, sort_keys=False))
    store.write("demo", "concepts.yaml", yaml.safe_dump({
        "schema": "tb/1", "concepts": [{
            "id": "c-one", "title": "概念一", "domain": "demo",
            "target_level": "L2",
        }],
    }, allow_unicode=True, sort_keys=False))
    store.write("demo", "exercises.yaml", yaml.safe_dump({
        "schema": "tb/1", "exercises": exercises,
    }, allow_unicode=True, sort_keys=False))
    store.write("demo", "resources.yaml", yaml.safe_dump({
        "schema": "tb/1", "resources": [resource()],
    }, allow_unicode=True, sort_keys=False))
    store.write("demo", "modules/M01/module.yaml", yaml.safe_dump({
        "schema": "tb/1", "id": "M01", "title": "模块", "priority": "P1",
        "concepts": ["c-one"], "lessons": ["L-1"], "order": 1,
    }, allow_unicode=True, sort_keys=False))

    manifest = {
        "schema": "tb/1", "id": "L-1", "title": "课", "module": "M01",
        "concepts": ["c-one"], "target_level": "L2", "minutes": 20,
        "objectives": ["目标"], "prerequisites": [],
        "exercises": [item["id"] for item in exercises],
        "resources": ["DOC-1"],
    }
    mounts = "".join(
        f'<div data-tb-exercise="{item["id"]}"></div>' for item in exercises
    )
    store.write(
        "demo", "modules/M01/lessons/L-1.html",
        '<script type="application/json" id="tb-manifest">\n'
        + json.dumps(manifest, ensure_ascii=False)
        + "\n</script>\n"
        + f'<article class="tb-lesson"><p>正文</p>{mounts}</article>',
    )
    store.set_step(
        "demo", "lessons", status="done", lesson_id="L-1",
        extra={"prompt_version": prompt_version},
    )
    plan = LessonPlan(
        "L-1", "课", 20, ["o"], [], module_id="M01", concepts=["c-one"],
    )
    return store, plan


def test_snapshot_records_metrics_and_path(tmp_path: Path) -> None:
    store, plan = setup_lesson(tmp_path)

    snapshot = snapshot_lesson(store, "demo", plan)
    saved = save_snapshot(store, snapshot)

    assert saved.startswith("history/L-1/")
    assert snapshot["schema"] == "studio-snapshot/1"
    assert snapshot["lesson_id"] == "L-1"
    assert snapshot["module_id"] == "M01"
    assert snapshot["prompt_version"] == "studio/2"
    assert snapshot["metrics"] == {
        "exercise_count": 1,
        "types": ["single_choice"],
        "levels": ["L2"],
        "max_level": "L2",
        "resource_count": 1,
        "trust": {"A": 1, "B": 0, "C": 0, "D": 0},
    } | {"html_hash": snapshot["metrics"]["html_hash"]}
    assert snapshot["metrics"]["exercise_count"] == 1
    assert snapshot["metrics"]["types"] == ["single_choice"]
    loaded = latest_snapshot(store, "demo", "L-1")
    assert loaded is not None
    assert loaded["metrics"] == snapshot["metrics"]
    assert loaded["html"] == snapshot["html"]
    assert loaded["exercises"] == snapshot["exercises"]
    assert loaded["resources"] == snapshot["resources"]
    assert lesson_metrics(store, "demo", plan) == snapshot["metrics"]
    assert list((store.path("demo") / "history" / "L-1").glob("*.tmp")) == []


def test_compare_snapshots_reports_changes(tmp_path: Path) -> None:
    before = {"metrics": {"exercise_count": 1, "types": ["single_choice"],
                          "max_level": "L2", "resource_count": 0,
                          "trust": {}, "html_hash": "a"},
              "prompt_version": "studio/1"}
    after = {"metrics": {"exercise_count": 2, "types": ["multi_choice", "single_choice"],
                         "max_level": "L3", "resource_count": 1,
                         "trust": {"A": 1}, "html_hash": "b"},
             "prompt_version": "studio/2"}

    changed = compare_snapshots(before, after)

    assert changed["html"] is True
    assert changed["exercise_count"] == 1
    assert changed["types_added"] == ["multi_choice"]
    assert changed["types_removed"] == []
    assert changed["max_level_before"] == "L2"
    assert changed["max_level_after"] == "L3"
    assert changed["resource_count"] == 1
    assert changed["prompt_version"] is True


def test_empty_lesson_snapshot_has_zero_metrics(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(draft_id="demo", topic="t", level="L2", lesson_count=1,
                 searches_per_lesson=5, model="m")
    plan = LessonPlan("L-1", "课", 20, ["o"], [], module_id="M01",
                      concepts=["c-one"])

    snapshot = snapshot_lesson(store, "demo", plan)
    assert snapshot["metrics"]["exercise_count"] == 0
    assert snapshot["metrics"]["types"] == []
    assert snapshot["metrics"]["max_level"] == ""
    assert snapshot["html"] == ""

    snapshot["metrics"]["exercise_count"] = 99
    again = snapshot_lesson(store, "demo", plan)
    assert again["metrics"]["exercise_count"] == 0


def test_snapshot_uses_lesson_prompt_version(tmp_path: Path) -> None:
    store, plan = setup_lesson(tmp_path, prompt_version="studio/1")
    assert snapshot_lesson(store, "demo", plan)["prompt_version"] == "studio/1"


def test_latest_snapshot_picks_newest(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(draft_id="demo", topic="t", level="L2", lesson_count=1,
                 searches_per_lesson=5, model="m")
    for created_at in (
        "2026-10-26T08:00:00+00:00",
        "2026-10-26T09:30:00+00:00",
        "2026-10-26T09:00:00+00:00",
    ):
        save_snapshot(store, {
            "schema": "studio-snapshot/1", "draft_id": "demo",
            "lesson_id": "L-1", "created_at": created_at,
            "prompt_version": "studio/2", "metrics": {},
        })

    assert latest_snapshot(store, "demo", "L-1")["created_at"] == (
        "2026-10-26T09:30:00+00:00"
    )
    assert latest_snapshot(store, "demo", "L-2") is None
    assert latest_snapshot(store, "demo", "../evil") is None


def test_snapshot_rejects_invalid_draft_id(tmp_path: Path) -> None:
    store, plan = setup_lesson(tmp_path)
    snapshot = snapshot_lesson(store, "demo", plan)

    broken = {**snapshot, "draft_id": "../x"}
    with pytest.raises(ValueError):
        save_snapshot(store, broken)

    assert latest_snapshot(store, "../x", "L-1") is None


def test_save_snapshot_serializes_yaml_dates(tmp_path: Path) -> None:
    store, plan = setup_lesson(tmp_path)
    resources = yaml.safe_load(store.read("demo", "resources.yaml"))
    resources["resources"][0]["last_verified"] = date(2026, 10, 25)
    store.write(
        "demo", "resources.yaml",
        yaml.safe_dump(resources, allow_unicode=True, sort_keys=False),
    )

    snapshot = snapshot_lesson(store, "demo", plan)
    assert isinstance(snapshot["resources"][0]["last_verified"], date)
    saved = save_snapshot(store, snapshot)

    assert saved.startswith("history/L-1/")
    loaded = latest_snapshot(store, "demo", "L-1")
    assert loaded["resources"][0]["last_verified"] == "2026-10-25"


def test_save_snapshot_normalizes_z_timestamp(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(draft_id="demo", topic="t", level="L2", lesson_count=1,
                 searches_per_lesson=5, model="m")
    snapshot = {
        "schema": "studio-snapshot/1", "draft_id": "demo",
        "lesson_id": "L-1", "created_at": "2026-10-26T09:30:00Z",
        "prompt_version": "studio/2", "metrics": {},
    }

    saved = save_snapshot(store, snapshot)

    assert saved == "history/L-1/20261026T093000000000Z.json"

    snapshot["created_at"] = "not-a-time"
    with pytest.raises(ValueError):
        save_snapshot(store, snapshot)


def test_draft_quality_is_none_for_incomplete_pack(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(draft_id="demo", topic="t", level="L2", lesson_count=1,
                 searches_per_lesson=5, model="m")

    assert draft_quality(store, "demo") is None


def test_draft_quality_reports_seeded_pack(tmp_path: Path) -> None:
    store, _ = setup_lesson(
        tmp_path, exercises=[single_choice(), multi_choice()],
    )
    store.write("demo", "research/L-1.json", json.dumps({
        "lesson_id": "L-1",
        "queries": ["q1", "q2", "q3"],
        "hits": [{
            "title": "Docs", "url": "https://docs.example/x", "trust": "A",
        }],
    }))

    quality = draft_quality(store, "demo")

    assert quality is not None
    assert quality["ok"] is True
    assert quality["possible"] > 0
    assert 0 <= quality["score"] <= quality["possible"]


def _draft_report(
    draft_id: str, lessons: list[str], *, ok: bool = True
) -> dict:
    return {
        "draft_id": draft_id,
        "error": None,
        "lessons": [{"lesson_id": item, "ok": ok} for item in lessons],
    }


def _wait_status(
    job: EvolutionJob, wanted: str, timeout: float = 5.0
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = job.status()
        if state["status"] == wanted:
            return state
        time.sleep(0.01)
    raise AssertionError(f"job did not reach {wanted}: {job.status()}")


def _wait_step(
    store: DraftStore,
    draft_id: str,
    step: str,
    wanted: str,
    timeout: float = 5.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        entry = store.load(draft_id)["steps"][step]
        if entry.get("status") == wanted:
            return
        time.sleep(0.01)
    raise AssertionError(
        f"{step} did not reach {wanted}: {store.load(draft_id)['steps'][step]}"
    )


def test_evolution_job_status_starts_idle(tmp_path: Path) -> None:
    store, _ = setup_lesson(tmp_path)
    job = EvolutionJob(store, JobRunner(store, inline=True))

    assert job.status() == {
        "status": "idle", "total": 0, "done": 0,
        "current": None, "results": [], "error": None,
    }


def test_evolution_job_runs_drafts_in_order(tmp_path: Path) -> None:
    store, _ = setup_lesson(tmp_path)
    runner = JobRunner(store, inline=True)
    job = EvolutionJob(store, runner)
    seen = []

    def process(draft_id, lessons):
        seen.append((draft_id, list(lessons)))
        return {"draft_id": draft_id, "error": None,
                "lessons": [{"lesson_id": item, "ok": True} for item in lessons]}

    job.start([("demo", ["L-1"])], process, inline=True)
    state = job.status()
    assert state["status"] == "done"
    assert seen == [("demo", ["L-1"])]
    assert state["done"] == 1


def test_evolution_job_counts_failed_lessons(tmp_path: Path) -> None:
    store, _ = setup_lesson(tmp_path)
    job = EvolutionJob(store, JobRunner(store, inline=True))

    def process(draft_id, lessons):
        return _draft_report(draft_id, lessons, ok=False)

    job.start([("demo", ["L-1", "L-2"])], process, inline=True)

    state = job.status()
    assert state["status"] == "failed"
    assert state["total"] == 2
    assert state["done"] == 2
    assert state["error"] == "1 个草稿失败"
    assert state["results"][0]["lessons"][1]["ok"] is False


def test_evolution_job_rejects_second_start(tmp_path: Path) -> None:
    store, _ = setup_lesson(tmp_path)
    job = EvolutionJob(store, JobRunner(store, inline=True))
    entered = threading.Event()
    release = threading.Event()

    def process(draft_id, lessons):
        entered.set()
        release.wait(timeout=5)
        return _draft_report(draft_id, lessons)

    job.start([("demo", ["L-1"])], process)
    assert entered.wait(timeout=5)
    with pytest.raises(EvolutionBusy):
        job.start([("demo", ["L-1"])], process)
    release.set()

    state = _wait_status(job, "done")
    assert state["done"] == 1
    assert state["results"] == [_draft_report("demo", ["L-1"])]


def test_evolution_job_continues_after_busy_draft(tmp_path: Path) -> None:
    store, _ = setup_lesson(tmp_path)
    store.create(draft_id="other", topic="t", level="L2", lesson_count=1,
                 searches_per_lesson=5, model="m")
    runner = JobRunner(store, inline=False)
    entered = threading.Event()
    release = threading.Event()

    def slow() -> None:
        entered.set()
        release.wait(timeout=5)

    runner.start("demo", "outline", slow)
    assert entered.wait(timeout=5)

    job = EvolutionJob(store, runner)
    seen = []

    def process(draft_id, lessons):
        seen.append(draft_id)
        return _draft_report(draft_id, lessons)

    try:
        job.start([("demo", ["L-1"]), ("other", ["L-2"])], process, inline=True)
    finally:
        release.set()
    _wait_step(store, "demo", "outline", "done")

    state = job.status()
    assert seen == ["other"]
    assert state["status"] == "failed"
    assert state["done"] == 1
    assert state["error"] == "1 个草稿失败"
    assert state["results"][0] == {
        "draft_id": "demo",
        "error": "草稿正在执行其他任务",
        "lessons": [],
    }
    assert state["results"][1] == _draft_report("other", ["L-2"])


@pytest.mark.parametrize("lessons", [None, [None], "L-1"])
def test_evolution_job_survives_malformed_report(
    tmp_path: Path, lessons: object
) -> None:
    store, _ = setup_lesson(tmp_path)
    job = EvolutionJob(store, JobRunner(store, inline=True))

    def process(draft_id, lesson_ids):
        return {"draft_id": draft_id, "error": None, "lessons": lessons}

    job.start([("demo", ["L-1"])], process, inline=True)

    state = job.status()
    assert state["status"] == "failed"
    assert state["done"] == 0
    assert state["results"] == [{
        "draft_id": "demo",
        "error": "草稿结果格式无效",
        "lessons": [],
    }]


def test_evolution_job_status_is_a_copy(tmp_path: Path) -> None:
    store, _ = setup_lesson(tmp_path)
    job = EvolutionJob(store, JobRunner(store, inline=True))

    state = job.status()
    state["results"].append("injected")
    state["status"] = "failed"

    assert job.status()["results"] == []
    assert job.status()["status"] == "idle"
