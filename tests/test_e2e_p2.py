import warnings
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

# Environment-level deprecation emitted by the installed FastAPI/Starlette pair.
warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.learning.rebuild import rebuild_state
from testbridge.learning.service import LearningService
from testbridge.learning.store import Goal, LearningStore
from web.app import create_app

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def test_learning_loop_end_to_end(tmp_path: Path) -> None:
    service = LearningService(
        load_pack(SAMPLE), EvidenceStore(tmp_path / "e.db"),
        LearningStore(tmp_path / "l.db"), now_fn=lambda: NOW,
    )
    for outcome in ["correct", "correct", "correct"]:
        event = replace(
            new_event(
                kind="exercise_attempt", lesson_id="L-SYNC-001",
                exercise_id="EX-SYNC-001", concept_ids=["sensor-time-sync"],
                outcome=outcome, score=1.0, max_score=1.0,
            ),
            created_at=NOW.isoformat(),
        )
        service.evidence.append(event)
    result = rebuild_state(service)
    assert result.events == 3
    assert result.concepts == 1
    assert result.reviews == 1
    assert service.store.get_mastery("local", "sensor-time-sync") is not None
    view = service.mastery("sensor-time-sync")
    assert view.exercise_observations == 3
    assert view.estimate == view.bkt_p
    assert service.store.list_reviews("local")
    readiness = service.readiness()
    assert readiness.total > 0
    assert "M01" in readiness.by_module
    service.store.set_goal(Goal(learner_id="local", daily_minutes=30))
    plan = service.today_plan()
    assert plan.budget_minutes == 30
    assert plan.items
    assert all(item.reason and item.estimated_minutes > 0 for item in plan.items)


def test_p2_web_pages_on_sample_pack(tmp_path: Path) -> None:
    c = TestClient(create_app(SAMPLE, tmp_path / "web.db"))
    assert c.get("/today").status_code == 200
    assert c.get("/concepts").status_code == 200
    assert c.get("/review").status_code == 200
    assert c.get("/progress").status_code == 200
    assert "Readiness" in c.get("/progress").text
    assert c.get("/").status_code == 200
