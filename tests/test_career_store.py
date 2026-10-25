from datetime import datetime, timezone
from pathlib import Path

from testbridge.career.store import TargetJd, TargetJdStore


def make_store(tmp_path: Path) -> TargetJdStore:
    return TargetJdStore(tmp_path / "target.db")


def test_missing_returns_none(tmp_path: Path) -> None:
    assert make_store(tmp_path).get() is None


def test_save_and_get_roundtrip(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(TargetJd(
        learner_id="local",
        source_text="招聘时间同步测试工程师",
        target_role="测试工程师",
        requirements=[{"text": "时间同步", "importance": "must",
                       "concepts": ["sensor-time-sync"], "rationale": "核心"}],
        weights={"sensor-time-sync": 1.6},
        model="fake",
    ))
    loaded = store.get()
    assert loaded is not None
    assert loaded.target_role == "测试工程师"
    assert loaded.weights == {"sensor-time-sync": 1.6}
    assert loaded.requirements[0]["concepts"] == ["sensor-time-sync"]
    assert loaded.updated_at


def test_save_refreshes_updated_at(tmp_path: Path, monkeypatch) -> None:
    instants = iter([
        datetime(2026, 10, 26, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 26, 1, 0, 1, tzinfo=timezone.utc),
    ])
    monkeypatch.setattr(
        "testbridge.career.store.utcnow", lambda: next(instants)
    )
    store = make_store(tmp_path)
    first = store.save(TargetJd(learner_id="local", source_text="first"))
    second = store.save(TargetJd(learner_id="local", source_text="second"))
    loaded = store.get()
    assert first.updated_at != second.updated_at
    assert loaded is not None
    assert loaded.updated_at == second.updated_at


def test_roundtrip_preserves_source_and_model(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(TargetJd(
        learner_id="local",
        source_text="招聘时间同步测试工程师",
        model="fake",
    ))
    loaded = store.get()
    assert loaded is not None
    assert loaded.source_text == "招聘时间同步测试工程师"
    assert loaded.model == "fake"


def test_save_overwrites_single_row(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(TargetJd(learner_id="local", source_text="first"))
    store.save(TargetJd(
        learner_id="local", source_text="second",
        weights={"clock-drift": 1.3},
    ))
    loaded = store.get()
    assert loaded is not None
    assert loaded.source_text == "second"
    assert loaded.weights == {"clock-drift": 1.3}
    assert store.count() == 1
