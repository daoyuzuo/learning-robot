from pathlib import Path

import pytest

from testbridge.studio.jobs import JobBusy, JobRunner
from testbridge.studio.store import DraftStore


def make(tmp_path: Path) -> tuple[DraftStore, JobRunner]:
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id="demo", topic="t", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    return store, JobRunner(store, inline=True)


def test_inline_job_marks_done(tmp_path: Path) -> None:
    store, runner = make(tmp_path)
    runner.start("demo", "outline", lambda: None)
    assert store.load("demo")["steps"]["outline"]["status"] == "done"


def test_failure_is_recorded(tmp_path: Path) -> None:
    store, runner = make(tmp_path)

    def boom() -> None:
        raise RuntimeError("bad")

    runner.start("demo", "outline", boom)
    step = store.load("demo")["steps"]["outline"]
    assert step["status"] == "failed"
    assert "bad" in step["error"]


def test_lesson_job_uses_lesson_key(tmp_path: Path) -> None:
    store, runner = make(tmp_path)
    runner.start("demo", "lessons", lambda: None, lesson_id="L-1")
    assert store.load("demo")["steps"]["lessons"]["L-1"]["status"] == "done"


def test_busy_job_is_rejected(tmp_path: Path) -> None:
    _store, runner = make(tmp_path)
    started = {"done": False}

    def slow() -> None:
        with pytest.raises(JobBusy):
            runner.start("demo", "outline", lambda: None)
        started["done"] = True

    runner.start("demo", "outline", slow)
    assert started["done"] is True


def test_batch_blocks_single_job(tmp_path: Path) -> None:
    store, runner = make(tmp_path)
    started = {"done": False}

    def batch() -> None:
        with pytest.raises(JobBusy):
            runner.start("demo", "outline", lambda: None)
        started["done"] = True

    runner.start_batch("demo", batch)
    assert started["done"] is True
    assert store.load("demo")["steps"]["batch"]["status"] == "done"


def test_single_job_blocks_batch(tmp_path: Path) -> None:
    store, runner = make(tmp_path)
    started = {"done": False}

    def single() -> None:
        with pytest.raises(JobBusy):
            runner.start_batch("demo", lambda: None)
        started["done"] = True

    runner.start("demo", "outline", single)
    assert started["done"] is True
    assert store.load("demo")["steps"]["outline"]["status"] == "done"


def test_batch_callback_can_fail_batch(tmp_path: Path) -> None:
    store, runner = make(tmp_path)

    def batch() -> None:
        store.set_step("demo", "batch", status="failed", error="1 课失败")

    runner.start_batch("demo", batch)

    step = store.load("demo")["steps"]["batch"]
    assert step["status"] == "failed"
    assert step["error"] == "1 课失败"
