import warnings
from pathlib import Path

from testbridge.build import build_pack
from testbridge.content.repository import load_pack
from testbridge.contract.validator import validate_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.exercise.grading import grade
from testbridge.lesson.renderer import render_lesson

# Environment-level deprecation emitted by the installed FastAPI/Starlette pair.
warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from web.app import create_app

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"


def sample_response(exercise):
    if exercise.type == "single_choice":
        return exercise.answer
    if exercise.type == "multi_choice":
        return exercise.answer
    if exercise.type == "short_answer":
        return exercise.answer.accepted[0]
    if exercise.type == "self_assess":
        return {"checked": [exercise.rubric[0].dimension]}
    return {"path": "data/artifacts/run.log", "checked": [exercise.rubric[0].dimension]}


def test_every_exercise_grades() -> None:
    pack = load_pack(SAMPLE)
    for exercise in pack.exercises.values():
        result = grade(exercise, sample_response(exercise))
        assert result.outcome in {"correct", "incorrect", "partial", "submitted"}


def test_every_lesson_renders_and_builds(tmp_path: Path) -> None:
    pack = load_pack(SAMPLE)
    assert validate_pack(SAMPLE).ok
    for lesson in pack.lessons_in_order():
        view = render_lesson(pack, lesson.manifest.id)
        assert "form class=\"tb-exercise\"" in view.body_html
    paths = build_pack(SAMPLE, tmp_path)
    assert len(paths) == 3
    assert all(path.is_file() for path in paths)


def test_evidence_round_trip(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "e.db")
    store.append(new_event(kind="exercise_attempt", concept_ids=["sensor-time-sync"]))
    path = tmp_path / "e.jsonl"
    assert store.export_jsonl(path) == 1
    assert store.import_jsonl(path) == 0


def test_web_smoke(tmp_path: Path) -> None:
    """Manual browser check: dashboard, lesson, and health respond."""
    pack = load_pack(SAMPLE)
    lesson_id = pack.lessons_in_order()[0].manifest.id
    client = TestClient(create_app(SAMPLE, tmp_path / "web.db"))
    assert client.get("/").status_code == 200
    assert client.get(f"/lesson/{lesson_id}").status_code == 200
    assert client.get("/api/health").status_code == 200
