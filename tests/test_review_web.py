import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore
from testbridge.tutor.client import TutorUpstreamError
from testbridge.tutor.config import TutorConfig
from testbridge.tutor.review_service import ReviewService
from testbridge.tutor.review_store import ExerciseReviewStore
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
REVIEW = (
    '{"verdict": "partial", "explanation": "方向对，但漏了重传代价。", '
    '"strengths": ["方向对"], "gaps": ["没提重传"], '
    '"rubric": [{"dimension": "机制", "met": true, "comment": "对"}, '
    '{"dimension": "场景", "met": false, "comment": "缺反例"}], '
    '"suggested_score": 0.5}'
)
TUTOR_REPLY = '{"answer": "x", "basis": "general"}'


class FakeClient:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        return self.reply


class ErrorClient:
    def complete(self, system: str, user: str) -> str:
        raise TutorUpstreamError("boom")


def make_app(tmp_path: Path, client=None) -> TestClient:
    pack = load_pack(SAMPLE)
    db = tmp_path / "e.db"
    evidence = EvidenceStore(db)
    shared = client or FakeClient(REVIEW)
    tutor = TutorService(pack, TutorStore(db), FakeClient(TUTOR_REPLY), CONFIG)
    reviewer = ReviewService(
        pack, evidence, ExerciseReviewStore(db), shared, CONFIG
    )
    return TestClient(create_app(SAMPLE, db, tutor=tutor, reviewer=reviewer))


def submit_short_answer(c: TestClient) -> str:
    response = c.post("/api/evidence", json={
        "lesson_id": "L-QOS-002",
        "exercise_id": "EX-QOS-005",
        "response": {"checked": ["机制"]},
    })
    assert response.status_code == 200
    return response.json()["evidence_id"]


def test_review_returns_reference_score(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    evidence_id = submit_short_answer(app)

    response = app.post("/api/review", json={"evidence_id": evidence_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"] == "partial"
    assert payload["suggested_score"] == 0.5
    assert payload["model"] == "demo-model"
    assert payload["cached"] is False
    assert payload["saved"] is True


def test_second_request_is_cached(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    evidence_id = submit_short_answer(app)
    app.post("/api/review", json={"evidence_id": evidence_id})

    payload = app.post("/api/review", json={"evidence_id": evidence_id}).json()

    assert payload["cached"] is True


def test_review_appends_llm_review_evidence(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    evidence_id = submit_short_answer(app)
    app.post("/api/review", json={"evidence_id": evidence_id})

    kinds = [row.kind for row in app.app.state.store.list(limit=10)]
    assert kinds.count("llm_review") == 1


def test_unknown_evidence_is_404(tmp_path: Path) -> None:
    response = make_app(tmp_path).post("/api/review", json={"evidence_id": "nope"})
    assert response.status_code == 404


def test_unsupported_evidence_is_400(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    evidence_id = submit_short_answer(app)
    app.post("/api/review", json={"evidence_id": evidence_id})
    llm_event = [
        row for row in app.app.state.store.list(limit=10)
        if row.kind == "llm_review"
    ][0]

    response = app.post("/api/review", json={"evidence_id": llm_event.id})

    assert response.status_code == 400


def test_upstream_error_is_502(tmp_path: Path) -> None:
    app = make_app(tmp_path, client=ErrorClient())
    evidence_id = submit_short_answer(app)
    response = app.post("/api/review", json={"evidence_id": evidence_id})
    assert response.status_code == 502


def test_disabled_reviewer_is_503(tmp_path: Path, monkeypatch) -> None:
    for name in (
        "TESTBRIDGE_LLM_BASE_URL",
        "TESTBRIDGE_LLM_API_KEY",
        "TESTBRIDGE_LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    app = TestClient(create_app(SAMPLE, tmp_path / "e.db"))
    response = app.post("/api/review", json={"evidence_id": "x"})
    assert response.status_code == 503
