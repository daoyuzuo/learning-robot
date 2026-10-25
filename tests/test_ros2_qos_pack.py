"""Acceptance checks for the real ROS 2 QoS content pack."""

import warnings
from pathlib import Path

# Environment-level deprecation emitted by the installed FastAPI/Starlette pair.
warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.content.repository import load_pack
from testbridge.contract.validator import validate_pack
from testbridge.lesson.renderer import render_lesson
from web.app import create_app

PACK_DIR = Path(__file__).parents[1] / "content-packs" / "ros2-qos"

CONCEPTS = {
    "ros2-communication-model",
    "dds-qos-policies",
    "qos-compatibility",
    "qos-observability",
    "qos-testing",
}
LESSONS = ["L-QOS-001", "L-QOS-002", "L-QOS-003"]


def test_pack_validates_without_errors_or_warnings() -> None:
    report = validate_pack(PACK_DIR)
    assert report.errors == []
    assert report.warnings == []


def test_pack_shape() -> None:
    pack = load_pack(PACK_DIR)
    assert set(pack.concepts) == CONCEPTS
    assert len(pack.exercises) == 6
    assert len(pack.resources) == 5
    assert [lesson.manifest.id for lesson in pack.lessons_in_order()] == LESSONS
    assert pack.modules["M01"].priority == "P0"


def test_every_concept_is_taught_and_exercised() -> None:
    pack = load_pack(PACK_DIR)
    taught = {
        concept_id
        for lesson in pack.lessons.values()
        for concept_id in lesson.manifest.concepts
    }
    exercised = {
        concept_id
        for exercise in pack.exercises.values()
        for concept_id in exercise.concepts
    }
    assert CONCEPTS <= taught
    assert CONCEPTS <= exercised


def test_every_lesson_has_objectives_exercises_and_resources() -> None:
    pack = load_pack(PACK_DIR)
    for lesson in pack.lessons.values():
        manifest = lesson.manifest
        assert manifest.objectives
        assert manifest.exercises
        assert manifest.resources


def test_lessons_render_forms_and_widget() -> None:
    pack = load_pack(PACK_DIR)
    view = render_lesson(pack, "L-QOS-002")

    assert 'data-exercise-id="EX-QOS-002"' in view.body_html
    assert 'data-exercise-id="EX-QOS-003"' in view.body_html
    assert 'data-exercise-id="EX-QOS-005"' in view.body_html
    assert 'data-widget-id="W-QOS-QUEUE"' in view.body_html
    assert "W-QOS-QUEUE" in {widget.widget.id for widget in view.widgets}
    assert "/assets/" not in view.body_html


def test_lesson_does_not_leak_answers() -> None:
    pack = load_pack(PACK_DIR)
    body = render_lesson(pack, "L-QOS-002").body_html
    assert '"answer":' not in body
    assert "正确答案" not in body
    assert "reliability" in body.lower()


def test_web_serves_pilot_pack(tmp_path: Path) -> None:
    app = create_app(PACK_DIR, tmp_path / "test.db")
    client = TestClient(app)

    lesson = client.get("/lesson/L-QOS-003")
    assert lesson.status_code == 200
    assert "QoS 观测与测试" in lesson.text
    assert client.get("/concepts").status_code == 200
    assert client.get("/today").status_code == 200


def test_submitting_an_answer_records_evidence(tmp_path: Path) -> None:
    app = create_app(PACK_DIR, tmp_path / "test.db")
    client = TestClient(app)

    response = client.post("/api/evidence", json={
        "lesson_id": "L-QOS-001", "exercise_id": "EX-QOS-001", "response": "c",
    })

    assert response.status_code == 200
    assert response.json()["grade"]["correct"] is True
    assert app.state.store.count() == 1
