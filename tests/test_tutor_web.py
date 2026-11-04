import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.content.repository import load_pack
from testbridge.search import SearchError, SearchHit
from testbridge.tutor.client import TutorTimeoutError, TutorUpstreamError
from testbridge.tutor.config import TutorConfig
from testbridge.tutor.service import TutorService
from testbridge.tutor.store import TutorStore
from web.app import create_app

SAMPLE = Path(__file__).parents[1] / "tests" / "fixtures" / "packs" / "ros2-qos"
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
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self.error is not None:
            raise self.error
        return self.reply


class FakeSearch:
    def __init__(self, hits) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        self.calls.append((query, count))
        return list(self.hits)

    def fetch(self, url: str) -> str:
        return ""


class BrokenSearch:
    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        raise SearchError("down")

    def fetch(self, url: str) -> str:
        return ""


def make_app(
    tmp_path: Path,
    client: FakeClient | None = None,
    *,
    search=None,
) -> TestClient:
    pack = load_pack(SAMPLE)
    service = TutorService(
        pack, TutorStore(tmp_path / "t.db"), client or FakeClient(), CONFIG,
        search=search,
    )
    return TestClient(create_app(SAMPLE, tmp_path / "e.db", tutor=service))


def test_lesson_page_renders_tutor_panel(tmp_path: Path) -> None:
    text = make_app(tmp_path).get("/lesson/L-QOS-002").text
    assert "追问" in text
    assert "整节课" in text
    assert "六类策略" in text
    assert "联网搜索不可用：未配置搜索服务" in text


def test_lesson_page_shows_web_status(tmp_path: Path) -> None:
    hit = SearchHit("外部依据", "https://example.com/a", "摘要", "", "正文", 3)
    text = make_app(tmp_path, search=FakeSearch([hit])).get(
        "/lesson/L-QOS-002"
    ).text
    assert "联网搜索：" in text
    assert "已开启" in text
    assert "tb-tutor-web-toggle" in text


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


def test_web_toggle_off_skips_search(tmp_path: Path) -> None:
    search = FakeSearch([])
    app = make_app(tmp_path, search=search)

    response = app.post("/api/tutor", json={
        "lesson_id": "L-QOS-002", "question": "为什么？", "web": False,
    })

    assert response.status_code == 200
    assert response.json()["web_used"] is False
    assert search.calls == []


def test_web_failure_falls_back(tmp_path: Path) -> None:
    app = make_app(tmp_path, search=BrokenSearch())

    response = app.post("/api/tutor", json={
        "lesson_id": "L-QOS-002", "question": "为什么？",
    })

    assert response.status_code == 200
    assert response.json()["web_used"] is False


def test_web_basis_and_link_are_rendered(tmp_path: Path) -> None:
    hit = SearchHit(
        "外部依据", "https://example.com/a", "摘要", "摘要", "正文", 3
    )
    client = FakeClient(
        '{"answer": "见外部资料。", "basis": "web", '
        '"citations": ["https://example.com/a"], "followups": []}'
    )
    app = make_app(tmp_path, client, search=FakeSearch([hit]))

    response = app.post("/api/tutor", json={
        "lesson_id": "L-QOS-002", "question": "最新做法？",
    })

    assert response.status_code == 200
    assert response.json()["web_used"] is True
    assert response.json()["citations"] == ["https://example.com/a"]
    assert response.json()["web_sources"][0]["trust"] == "A"

    page = app.get("/lesson/L-QOS-002").text
    assert "联网搜索" in page
    assert "网络来源" in page
    assert 'href="https://example.com/a"' in page


def test_history_is_shown_after_reload(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    app.post("/api/tutor", json={
        "lesson_id": "L-QOS-002", "question": "为什么？",
    })

    text = app.get("/lesson/L-QOS-002").text

    assert "为什么？" in text
    assert "因为订阅请求的可靠性更高。" in text


def test_selection_is_accepted_and_persisted(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    response = app.post("/api/tutor", json={
        "lesson_id": "L-QOS-002",
        "question": "这句什么意思？",
        "selection": "可靠性更高的订阅",
    })

    assert response.status_code == 200
    stored = app.app.state.tutor.history("L-QOS-002")
    assert any(message.selection == "可靠性更高的订阅" for message in stored)


def test_oversized_selection_is_truncated_not_rejected(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    response = app.post("/api/tutor", json={
        "lesson_id": "L-QOS-002", "question": "问", "selection": "一" * 2000,
    })

    assert response.status_code == 200
    stored = app.app.state.tutor.history("L-QOS-002")
    assert all(len(message.selection) <= 400 for message in stored)
