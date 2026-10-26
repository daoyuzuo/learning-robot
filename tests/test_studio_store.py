import os
from pathlib import Path

import pytest

from testbridge.studio.store import (
    DraftError,
    DraftNotFound,
    DraftStore,
    _process_alive,
)


def make_store(tmp_path: Path) -> DraftStore:
    return DraftStore(tmp_path / "drafts")


def create(store: DraftStore, draft_id: str = "demo-pack") -> dict:
    return store.create(
        draft_id=draft_id, topic="ROS 2 执行器", level="L3",
        lesson_count=2, searches_per_lesson=20,
        model="deepseek-chat", prompt_version="studio/1",
    )


def test_create_writes_draft_json(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    draft = create(store)

    assert draft["schema"] == "studio/1"
    assert draft["steps"]["outline"]["status"] == "pending"
    assert draft["steps"]["research"] == {}
    assert (tmp_path / "drafts" / "demo-pack" / "draft.json").is_file()
    assert store.load("demo-pack")["topic"] == "ROS 2 执行器"


def test_rejects_bad_and_duplicate_ids(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(DraftError):
        store.create(
            draft_id="../evil", topic="x", level="L2", lesson_count=1,
            searches_per_lesson=5, model="m", prompt_version="v",
        )
    create(store)
    with pytest.raises(DraftError):
        create(store)


def test_set_step_updates_draft_and_timestamp(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    create(store)

    store.set_step("demo-pack", "outline", status="done")

    draft = store.load("demo-pack")
    assert draft["steps"]["outline"]["status"] == "done"
    assert draft["steps"]["outline"]["at"]
    assert draft["updated_at"]


def test_set_lesson_step_creates_entry(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    create(store)

    store.set_step(
        "demo-pack", "research", status="running", lesson_id="L-1", extra={"queries": 3}
    )

    assert store.load("demo-pack")["steps"]["research"]["L-1"]["status"] == "running"
    assert store.load("demo-pack")["steps"]["research"]["L-1"]["queries"] == 3


def test_mark_interrupted_flips_running(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    create(store)
    store.set_step("demo-pack", "outline", status="running")

    assert store.mark_interrupted() == 1
    step = store.load("demo-pack")["steps"]["outline"]
    assert step["status"] == "failed"
    assert step["error"] == "interrupted"


def test_running_step_records_its_owner_and_pid(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts", instance_id="owner-a", pid=4242)
    create(store)

    store.set_step("demo-pack", "lessons", status="running", lesson_id="L-1")

    step = store.load("demo-pack")["steps"]["lessons"]["L-1"]
    assert step["owner"] == "owner-a"
    assert step["pid"] == 4242

    store.set_step("demo-pack", "lessons", status="done", lesson_id="L-1")
    step = store.load("demo-pack")["steps"]["lessons"]["L-1"]
    assert "owner" not in step
    assert "pid" not in step


def test_mark_interrupted_keeps_a_live_other_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = DraftStore(tmp_path / "drafts", instance_id="owner-a", pid=4242)
    create(first)
    first.set_step("demo-pack", "outline", status="running")
    second = DraftStore(tmp_path / "drafts", instance_id="owner-b", pid=5252)
    monkeypatch.setattr(
        "testbridge.studio.store._process_alive", lambda pid: pid == 4242
    )

    assert second.mark_interrupted() == 0
    assert second.load("demo-pack")["steps"]["outline"]["status"] == "running"


def test_mark_interrupted_flips_a_dead_other_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = DraftStore(tmp_path / "drafts", instance_id="owner-a", pid=4242)
    create(first)
    first.set_step("demo-pack", "outline", status="running")
    second = DraftStore(tmp_path / "drafts", instance_id="owner-b", pid=5252)
    monkeypatch.setattr("testbridge.studio.store._process_alive", lambda pid: False)

    assert second.mark_interrupted() == 1
    step = second.load("demo-pack")["steps"]["outline"]
    assert step["status"] == "failed"
    assert step["error"] == "interrupted"


def test_mark_interrupted_flips_a_stale_owner_in_the_same_process(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    create(store)
    store.set_step("demo-pack", "outline", status="running")
    restarted = DraftStore(tmp_path / "drafts")

    assert restarted.mark_interrupted() == 1
    assert restarted.load("demo-pack")["steps"]["outline"]["status"] == "failed"


def test_process_alive_recognizes_this_process_and_missing_pids() -> None:
    assert _process_alive(os.getpid()) is True
    assert _process_alive(0) is False
    assert _process_alive(2**31 - 1) is False


def test_write_and_read_files(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    create(store)

    store.write("demo-pack", "outline.html", "<article>x</article>")

    assert store.read("demo-pack", "outline.html") == "<article>x</article>"


def test_load_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(DraftNotFound):
        make_store(tmp_path).load("nope")


def test_list_returns_drafts_sorted(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    create(store, "b-pack")
    create(store, "a-pack")
    assert [draft["id"] for draft in store.list()] == ["a-pack", "b-pack"]


def test_search_backend_defaults_and_validates(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    draft = create(store)
    assert draft["search_backend"] == "auto"

    with pytest.raises(DraftError):
        store.create(
            draft_id="bad-backend", topic="t", level="L2", lesson_count=1,
            searches_per_lesson=5, model="m", prompt_version="studio/1",
            search_backend="bogus",
        )


def test_module_fields_default_and_validate(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    draft = store.create(
        draft_id="multi", topic="t", level="L2",
        module_count=2, lessons_per_module=3, searches_per_lesson=5,
        model="m", prompt_version="studio/1",
    )
    assert draft["module_count"] == 2
    assert draft["lessons_per_module"] == 3
    assert draft["lesson_count"] == 6

    with pytest.raises(DraftError) as excinfo:
        store.create(
            draft_id="bad-modules", topic="t", level="L2",
            module_count=4, lessons_per_module=1, searches_per_lesson=5,
            model="m", prompt_version="studio/1",
        )
    assert excinfo.value.code == "invalid_module_count"


def test_legacy_lesson_count_still_works(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    draft = store.create(
        draft_id="legacy", topic="t", level="L2", lesson_count=2,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    assert draft["module_count"] == 1
    assert draft["lessons_per_module"] == 2
    assert draft["lesson_count"] == 2


def test_rejects_inconsistent_lesson_count(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(DraftError) as excinfo:
        store.create(
            draft_id="mismatch", topic="t", level="L2",
            module_count=2, lessons_per_module=2, lesson_count=3,
            searches_per_lesson=5, model="m", prompt_version="studio/1",
        )
    assert excinfo.value.code == "invalid_lesson_count"


def test_rejects_bad_lessons_per_module(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(DraftError) as excinfo:
        store.create(
            draft_id="too-many-lessons", topic="t", level="L2",
            module_count=1, lessons_per_module=6,
            searches_per_lesson=5, model="m", prompt_version="studio/1",
        )
    assert excinfo.value.code == "invalid_lessons_per_module"


def test_create_without_plan_keeps_old_shape(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    draft = store.create(
        draft_id="demo", topic="t", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m",
    )
    assert "plan" not in draft


def test_create_with_plan_persists_it(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    plan = {
        "inputs": {"weekly_hours": 2, "horizon_weeks": 2,
                   "purpose": "systematic", "must_cover": []},
        "computed": {"module_count": 1, "lessons_per_module": 3,
                     "lesson_minutes": 30, "total_lessons": 3},
        "rationale": "r", "guidance": [], "confirmed": False,
        "updated_at": "2026-10-27T00:00:00+00:00", "messages": [],
    }
    store.create(
        draft_id="demo", topic="t", level="L2", module_count=1,
        lessons_per_module=3, searches_per_lesson=5, model="m", plan=plan,
    )
    assert store.load("demo")["plan"]["computed"]["total_lessons"] == 3


def test_create_with_invalid_plan_raises_draft_error(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    bad = {
        "computed": {"module_count": 4, "lessons_per_module": 1,
                     "lesson_minutes": 30, "total_lessons": 4},
    }
    with pytest.raises(DraftError) as excinfo:
        store.create(
            draft_id="bad-plan", topic="t", level="L2", module_count=1,
            lessons_per_module=1, searches_per_lesson=5, model="m", plan=bad,
        )
    assert excinfo.value.code == "plan_invalid"
    assert store.exists("bad-plan") is False
