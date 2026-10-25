import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.learning.store import ReviewState
from web.app import create_app

SAMPLE = Path(__file__).parents[1] / "content-packs" / "ros2-qos"


def make_app(tmp_path: Path) -> TestClient:
    return TestClient(create_app(SAMPLE, tmp_path / "e.db"))


def seed(app: TestClient, exercise_id: str, due: str, concepts: list[str]) -> None:
    app.app.state.learning.store.upsert_review(ReviewState(
        learner_id="local", exercise_id=exercise_id, concept_ids=concepts,
        due=due, stability=1.0, difficulty=5.0, reps=1, lapses=0,
        state="Review", last_review=None,
        card_json={
            "card_id": 1, "state": 2, "step": 0, "stability": 1.0,
            "difficulty": 5.0, "due": due, "last_review": None,
        },
    ))


def test_empty_session_shows_message(tmp_path: Path) -> None:
    text = make_app(tmp_path).get("/review/session").text
    assert "今天没有到期卡" in text


def test_session_orders_cards_by_due(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed(app, "EX-QOS-001", "2020-01-02T00:00:00+00:00", ["ros2-communication-model"])
    seed(app, "EX-QOS-006", "2020-01-01T00:00:00+00:00", ["qos-testing"])

    text = app.get("/review/session").text

    assert "共 2 张" in text
    assert text.index('data-exercise-id="EX-QOS-006"') < text.index(
        'data-exercise-id="EX-QOS-001"'
    )


def test_session_forms_carry_their_own_lesson(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed(app, "EX-QOS-001", "2020-01-01T00:00:00+00:00", ["ros2-communication-model"])
    seed(app, "EX-QOS-006", "2020-01-02T00:00:00+00:00", ["qos-testing"])

    text = app.get("/review/session").text

    assert 'data-lesson-id="L-QOS-001"' in text
    assert 'data-lesson-id="L-QOS-003"' in text


def test_cross_lesson_submission_succeeds(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed(app, "EX-QOS-001", "2020-01-01T00:00:00+00:00", ["ros2-communication-model"])
    seed(app, "EX-QOS-006", "2020-01-02T00:00:00+00:00", ["qos-testing"])

    first = app.post("/api/evidence", json={
        "lesson_id": "L-QOS-001", "exercise_id": "EX-QOS-001", "response": "c",
    })
    second = app.post("/api/evidence", json={
        "lesson_id": "L-QOS-003", "exercise_id": "EX-QOS-006", "response": "b",
    })

    assert first.status_code == 200
    assert second.status_code == 200


def test_unknown_exercise_is_skipped_with_note(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed(app, "EX-NOPE", "2020-01-01T00:00:00+00:00", ["qos-testing"])

    text = app.get("/review/session").text

    assert "1 张卡对应的练习已不存在" in text
    assert "data-exercise-id=\"EX-NOPE\"" not in text


def test_review_page_links_to_session(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    seed(app, "EX-QOS-001", "2020-01-01T00:00:00+00:00", ["ros2-communication-model"])

    assert 'href="/review/session"' in app.get("/review").text
