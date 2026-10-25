from datetime import date, timedelta
from pathlib import Path

import pytest

from testbridge.career.applications import (
    STATUSES,
    ApplicationError,
    ApplicationStore,
)


def make_store(tmp_path: Path) -> ApplicationStore:
    return ApplicationStore(tmp_path / "apps.db")


def today(offset: int = 0) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def test_create_and_get(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    app = store.create(
        company="某机器人公司", role="测试工程师",
        source="内推", status="applied", applied_at=today(),
        next_action="补发简历", next_action_at=today(1),
        notes="HR 说一周内回复",
    )
    loaded = store.get(app.id)
    assert loaded is not None
    assert loaded.company == "某机器人公司"
    assert loaded.status == "applied"
    assert loaded.next_action_at == today(1)
    assert loaded.created_at and loaded.updated_at


def test_create_rejects_empty_company_or_role(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ApplicationError, match="公司"):
        store.create(company="  ", role="测试")
    with pytest.raises(ApplicationError, match="岗位"):
        store.create(company="某公司", role="")


def test_create_rejects_bad_status_and_date(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ApplicationError, match="状态"):
        store.create(company="c", role="r", status="unknown")
    with pytest.raises(ApplicationError, match="日期"):
        store.create(company="c", role="r", applied_at="2026/10/26")
    with pytest.raises(ApplicationError, match="日期"):
        store.create(company="c", role="r", next_action_at="2026-1-1")


def test_long_text_is_truncated(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    app = store.create(company="c" * 300, role="r", notes="n" * 6000)
    assert len(app.company) == 200
    assert len(app.notes) == 5000


def test_update_changes_fields_and_refreshes_time(tmp_path: Path, monkeypatch) -> None:
    from datetime import datetime, timezone

    instants = iter([
        datetime(2026, 10, 26, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 26, 2, 0, 0, tzinfo=timezone.utc),
    ])
    monkeypatch.setattr(
        "testbridge.career.applications.utcnow", lambda: next(instants)
    )
    store = make_store(tmp_path)
    app = store.create(company="c", role="r")
    updated = store.update(app.id, status="interviewing", notes="约了下周")
    assert updated.status == "interviewing"
    assert updated.notes == "约了下周"
    assert updated.updated_at != app.updated_at
    assert store.get(app.id).updated_at == updated.updated_at


def test_update_unknown_and_unknown_field(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ApplicationError, match="不存在"):
        store.update("nope", status="applied")
    app = store.create(company="c", role="r")
    with pytest.raises(ApplicationError, match="字段"):
        store.update(app.id, bogus="x")


def test_list_filters_and_counts(tmp_path: Path, monkeypatch) -> None:
    from datetime import datetime, timezone

    instants = iter([
        datetime(2026, 10, 26, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 26, 2, 0, 0, tzinfo=timezone.utc),
    ])
    monkeypatch.setattr(
        "testbridge.career.applications.utcnow", lambda: next(instants)
    )
    store = make_store(tmp_path)
    store.create(company="a", role="r", status="applied")
    store.create(company="b", role="r", status="offer")
    assert [item.company for item in store.list()] == ["b", "a"]
    assert [item.company for item in store.list(status="applied")] == ["a"]
    counts = store.counts()
    assert counts["applied"] == 1
    assert counts["offer"] == 1
    assert counts["draft"] == 0


def test_due_excludes_terminal_and_future(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    due = store.create(company="a", role="r", status="applied",
                       next_action_at=today(-1))
    store.create(company="b", role="r", status="offer",
                 next_action_at=today(-1))
    store.create(company="c", role="r", status="applied",
                 next_action_at=today(3))
    assert [item.id for item in store.due(today())] == [due.id]


def test_withdraw_is_idempotent(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    app = store.create(company="c", role="r", status="applied")
    assert store.withdraw(app.id).status == "withdrawn"
    assert store.withdraw(app.id).status == "withdrawn"
