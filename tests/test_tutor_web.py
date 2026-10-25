import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.content.repository import load_pack
from testbridge.tutor.client import TutorTimeoutError, TutorUpstreamError
from testbridge.tutor.config import TutorConfig
from testbridge.tutor.service import TutorService
from testbridge.tutor.store import TutorStore
from web.app import create_app

SAMPLE = Path(__file__).parents[1] / "content-packs" / "ros2-qos"
CONFIG = TutorConfig(
    base_url="https://api.example.com/v1",
    api_key="sk-test",
    model="demo-model",
    timeout=5.0,
)
REPLY = (
    '{"answer": "因为订阅请求的可靠性更高。", "basis": "lesson", '
    '"citations": ["兼容性：Request vs Offered"], "followups": []}'
)


class FakeClient:
    def __init__(self, reply: str = REPLY, error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error

    def complete(self, system: str, user: str) -> str:
        if self.error is not None:
            raise self.error
        return self.reply


def make_app(tmp_path: Path, client: FakeClient | None = None) -> TestClient:
    pack = load_pack(SAMPLE)
    service = TutorService(
        pack, TutorStore(tmp_path / "t.db"), client or FakeClient(), CONFIG
    )
    return TestClient(create_app(SAMPLE, tmp_path / "e.db", tutor=service))


def test_lesson_page_renders_tutor_panel(tmp_path: Path) -> None:
    text = make_app(tmp_path).get("/lesson/L-QOS-002").text
    assert "追问" in text
    assert "整节课" in text
    assert "六类策略" in text


def test_ask_returns_labeled_answer(tmp_path: Path) -> None:
    response = make_app(tmp_path).post("/api/tutor", json={
        "lesson_id": "L-QOS-002",
        "anchor": "兼容性：Request vs Offered",
        "question": "为什么订阅要求高就不连？",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["basis"] == "lesson"
    assert payload["answer"].startswith("因为")
    assert payload["citations"] == ["兼容性：Request vs Offered"]
    assert payload["saved"] is True


def test_unknown_lesson_is_404(tmp_path: Path) -> None:
    response = make_app(tmp_path).post("/api/tutor", json={
        "lesson_id": "L-NOPE", "question": "问题",
    })
    assert response.status_code == 404


def test_empty_question_is_400(tmp_path: Path) -> None:
    response = make_app(tmp_path).post("/api/tutor", json={
        "lesson_id": "L-QOS-002", "question": "  ",
    })
    assert response.status_code == 400


def test_upstream_error_is_502(tmp_path: Path) -> None:
    app = make_app(tmp_path, FakeClient(error=TutorUpstreamError("boom")))
    response = app.post("/api/tutor", json={
        "lesson_id": "L-QOS-002", "question": "问题",
    })
    assert response.status_code == 502
    assert "sk-test" not in response.text


def test_timeout_is_504(tmp_path: Path) -> None:
    app = make_app(tmp_path, FakeClient(error=TutorTimeoutError()))
    response = app.post("/api/tutor", json={
        "lesson_id": "L-QOS-002", "question": "问题",
    })
    assert response.status_code == 504


def test_disabled_tutor_is_503_and_panel_explains(
    tmp_path: Path, monkeypatch
) -> None:
    for name in (
        "TESTBRIDGE_LLM_BASE_URL",
        "TESTBRIDGE_LLM_API_KEY",
        "TESTBRIDGE_LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    app = TestClient(create_app(SAMPLE, tmp_path / "e.db"))
    response = app.post("/api/tutor", json={
        "lesson_id": "L-QOS-002", "question": "问题",
    })
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "tutor_disabled"

    page = app.get("/lesson/L-QOS-002").text
    assert "TESTBRIDGE_LLM_BASE_URL" in page


def test_asking_does_not_touch_learning_state(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    before_evidence = app.app.state.store.count()
    before_mastery = app.app.state.learning.all_mastery()

    app.post("/api/tutor", json={
        "lesson_id": "L-QOS-002", "question": "为什么？",
    })

    assert app.app.state.store.count() == before_evidence
    assert app.app.state.learning.all_mastery() == before_mastery


def test_history_is_shown_after_reload(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    app.post("/api/tutor", json={
        "lesson_id": "L-QOS-002", "question": "为什么？",
    })

    text = app.get("/lesson/L-QOS-002").text

    assert "为什么？" in text
    assert "因为订阅请求的可靠性更高。" in text
