import json
import re
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from testbridge.tutor.client import TutorUpstreamError
from testbridge.tutor.config import TutorConfig
from web.app import create_app

ROOT = Path(__file__).parents[1]
SAMPLE = ROOT / "content-packs" / "sample-sensors"
BANKS = ROOT / "interview-banks"


def make_app(tmp_path: Path, llm=None, config=None) -> TestClient:
    return TestClient(create_app(
        SAMPLE, tmp_path / "i.db",
        interview_banks=BANKS,
        interview_llm=llm,
        interview_config=config,
    ))


CONFIG = TutorConfig(base_url="http://x", api_key="k", model="fake")


class FakeClient:
    """Reply with one valid dimension per rubric line in the prompt."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        dimensions = re.findall(r"^- (.+?)（权重", user, flags=re.MULTILINE)
        return json.dumps({
            "scores": [
                {"dimension": dimension, "score": 0.6, "rationale": "ok"}
                for dimension in dimensions
            ],
            "summary": "继续", "strengths": [], "gaps": [],
        }, ensure_ascii=False)


def start_session(c: TestClient) -> str:
    response = c.post("/interview", data={"question_count": "3"},
                      follow_redirects=False)
    return response.headers["location"].rsplit("/", 1)[-1]


def test_interview_page_lists_weak_concepts(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    response = c.get("/interview")
    assert response.status_code == 200
    assert "开始模拟" in response.text
    assert "timestamp-basics" in response.text or "时间戳基础" in response.text


def test_start_redirects_to_session(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    response = c.post("/interview", data={"question_count": "3"},
                      follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/interview/session/")


def test_nav_shows_interview(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    assert 'href="/interview"' in c.get("/").text


def test_session_page_renders_question(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient())
    session_id = start_session(c)
    response = c.get(f"/interview/session/{session_id}")
    assert response.status_code == 200
    assert "1 / 3" in response.text
    assert "提交评分" in response.text


def test_draft_and_grade_api(tmp_path: Path) -> None:
    client = FakeClient()
    c = make_app(tmp_path, llm=client, config=CONFIG)
    session_id = start_session(c)
    page = c.get(f"/interview/session/{session_id}").text
    question_id = page.split('data-question-id="')[1].split('"')[0]
    saved = c.put(
        f"/api/interview/session/{session_id}/answer",
        json={"question_id": question_id, "answer": "我的回答"},
    )
    assert saved.status_code == 200
    graded = c.post(
        f"/api/interview/session/{session_id}/grade",
        json={"question_id": question_id},
    )
    assert graded.status_code == 200
    assert graded.json()["mode"] == "llm"
    assert graded.json()["scores"]


def test_reset_and_abandon(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient())
    session_id = start_session(c)
    page = c.get(f"/interview/session/{session_id}").text
    question_id = page.split('data-question-id="')[1].split('"')[0]
    c.put(f"/api/interview/session/{session_id}/answer",
          json={"question_id": question_id, "answer": "x"})
    assert c.post(f"/api/interview/session/{session_id}/reset",
                  json={"question_id": question_id}).status_code == 200
    assert c.post(f"/api/interview/session/{session_id}/abandon",
                  json={}).status_code == 200
    assert "会话已结束" in c.get(f"/interview/session/{session_id}").text


def test_bank_missing_disables_interview(tmp_path: Path) -> None:
    c = TestClient(create_app(
        SAMPLE, tmp_path / "i.db", interview_banks=tmp_path / "nope",
    ))
    page = c.get("/interview")
    assert page.status_code == 200
    assert "题库不可用" in page.text
    assert 'href="/interview"' not in c.get("/").text
    assert c.post("/interview", data={"question_count": "3"}).status_code == 503


def test_bank_malformed_shows_error(tmp_path: Path) -> None:
    banks = tmp_path / "banks"
    banks.mkdir()
    (banks / "sample-sensors.yaml").write_text(
        "schema: tb-interview/1\npack: sample-sensors\nquestions: []\n",
        encoding="utf-8",
    )
    c = TestClient(create_app(
        SAMPLE, tmp_path / "i.db", interview_banks=banks,
    ))
    response = c.get("/interview")
    assert response.status_code == 200
    assert "题库结构无效" in response.text
    assert c.post("/interview", data={"question_count": "3"}).status_code == 503


class ErrorClient:
    def complete(self, system: str, user: str) -> str:
        raise TutorUpstreamError("boom")


def test_grade_maps_upstream_error_to_502(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=ErrorClient(), config=CONFIG)
    session_id = start_session(c)
    question_id = c.get(f"/interview/session/{session_id}").text.split(
        'data-question-id="'
    )[1].split('"')[0]
    c.put(f"/api/interview/session/{session_id}/answer",
          json={"question_id": question_id, "answer": "答案"})
    response = c.post(
        f"/api/interview/session/{session_id}/grade",
        json={"question_id": question_id},
    )
    assert response.status_code == 502
    assert "模型服务不可用" in response.text


def test_session_page_shows_grading_card(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    session_id = start_session(c)
    question_id = c.get(f"/interview/session/{session_id}").text.split(
        'data-question-id="'
    )[1].split('"')[0]
    c.put(f"/api/interview/session/{session_id}/answer",
          json={"question_id": question_id, "answer": "答案"})
    c.post(f"/api/interview/session/{session_id}/grade",
           json={"question_id": question_id})
    page = c.get(f"/interview/session/{session_id}").text
    assert "评分建议" in page
    assert 'data-dimension="' in page


def test_stale_session_returns_503_when_bank_missing(tmp_path: Path) -> None:
    db = tmp_path / "i.db"
    first = TestClient(create_app(
        SAMPLE, db, interview_banks=BANKS,
        interview_llm=FakeClient(), interview_config=CONFIG,
    ))
    session_id = start_session(first)
    second = TestClient(create_app(
        SAMPLE, db, interview_banks=tmp_path / "nope",
    ))
    assert second.get(f"/interview/session/{session_id}").status_code == 503


def confirm_payload(question_id: str, graded: dict, score: float = 0.6) -> dict:
    return {
        "question_id": question_id,
        "scores": [
            {"dimension": item["dimension"], "score": score}
            for item in graded["scores"]
        ],
        "duration_ms": 1000,
    }


def test_confirm_writes_evidence_and_summary(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    session_id = start_session(c)
    page = c.get(f"/interview/session/{session_id}").text
    question_id = page.split('data-question-id="')[1].split('"')[0]
    c.put(f"/api/interview/session/{session_id}/answer",
          json={"question_id": question_id, "answer": "我的回答"})
    graded = c.post(
        f"/api/interview/session/{session_id}/grade",
        json={"question_id": question_id},
    ).json()
    payload = confirm_payload(question_id, graded)
    confirmed = c.post(
        f"/api/interview/session/{session_id}/confirm", json=payload
    )
    assert confirmed.status_code == 200
    evidence_id = confirmed.json()["evidence_id"]
    assert evidence_id
    repeated = c.post(
        f"/api/interview/session/{session_id}/confirm", json=payload
    )
    assert repeated.json()["evidence_id"] == evidence_id
    summary = c.get(f"/interview/session/{session_id}/summary")
    assert summary.status_code == 200
    assert "0.60" in summary.text
    assert "我的回答" in summary.text


def test_progress_shows_interview_evidence(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    session_id = start_session(c)
    page = c.get(f"/interview/session/{session_id}").text
    question_id = page.split('data-question-id="')[1].split('"')[0]
    c.put(f"/api/interview/session/{session_id}/answer",
          json={"question_id": question_id, "answer": "答案"})
    graded = c.post(
        f"/api/interview/session/{session_id}/grade",
        json={"question_id": question_id},
    ).json()
    c.post(
        f"/api/interview/session/{session_id}/confirm",
        json=confirm_payload(question_id, graded),
    )
    text = c.get("/progress").text
    assert re.search(r"<td>\s*面试\s*</td>", text)
    assert f"/interview/session/{session_id}/summary" in text


def test_three_question_flow_reaches_today(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    session_id = start_session(c)
    evidence_ids = set()
    for _ in range(3):
        page = c.get(f"/interview/session/{session_id}").text
        question_id = page.split('data-question-id="')[1].split('"')[0]
        c.put(f"/api/interview/session/{session_id}/answer",
              json={"question_id": question_id, "answer": "我的回答"})
        graded = c.post(
            f"/api/interview/session/{session_id}/grade",
            json={"question_id": question_id},
        ).json()
        response = c.post(
            f"/api/interview/session/{session_id}/confirm",
            json={
                "question_id": question_id,
                "scores": [
                    {"dimension": item["dimension"], "score": 0.2}
                    for item in graded["scores"]
                ],
            },
        )
        assert response.status_code == 200
        evidence_ids.add(response.json()["evidence_id"])
    assert len(evidence_ids) == 3
    summary = c.get(f"/interview/session/{session_id}/summary")
    assert summary.status_code == 200
    assert "completed" in summary.text
    today = c.get("/today").text
    assert "面试失分" in today


def test_session_resumes_after_app_restart(tmp_path: Path) -> None:
    db = tmp_path / "i.db"
    first = TestClient(create_app(
        SAMPLE, db, interview_banks=BANKS,
        interview_llm=FakeClient(), interview_config=CONFIG,
    ))
    session_id = start_session(first)
    page = first.get(f"/interview/session/{session_id}").text
    question_id = page.split('data-question-id="')[1].split('"')[0]
    first.put(f"/api/interview/session/{session_id}/answer",
              json={"question_id": question_id, "answer": "重启前的回答"})
    second = TestClient(create_app(
        SAMPLE, db, interview_banks=BANKS,
        interview_llm=FakeClient(), interview_config=CONFIG,
    ))
    resumed = second.get(f"/interview/session/{session_id}").text
    assert question_id in resumed
    assert "重启前的回答" in resumed


class BadJsonClient:
    def complete(self, system: str, user: str) -> str:
        return "not json"


def test_manual_scoring_flow_writes_evidence(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=BadJsonClient(), config=CONFIG)
    session_id = start_session(c)
    page = c.get(f"/interview/session/{session_id}").text
    question_id = page.split('data-question-id="')[1].split('"')[0]
    c.put(f"/api/interview/session/{session_id}/answer",
          json={"question_id": question_id, "answer": "答案"})
    graded = c.post(
        f"/api/interview/session/{session_id}/grade",
        json={"question_id": question_id},
    ).json()
    assert graded["mode"] == "manual"
    confirmed = c.post(
        f"/api/interview/session/{session_id}/confirm",
        json=confirm_payload(question_id, graded, score=0.6),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["evidence_id"]


def test_malformed_duration_is_400(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    session_id = start_session(c)
    page = c.get(f"/interview/session/{session_id}").text
    question_id = page.split('data-question-id="')[1].split('"')[0]
    c.put(f"/api/interview/session/{session_id}/answer",
          json={"question_id": question_id, "answer": "答案"})
    graded = c.post(
        f"/api/interview/session/{session_id}/grade",
        json={"question_id": question_id},
    ).json()
    response = c.post(
        f"/api/interview/session/{session_id}/confirm",
        json={
            "question_id": question_id,
            "scores": [
                {"dimension": item["dimension"], "score": 0.6}
                for item in graded["scores"]
            ],
            "duration_ms": {},
        },
    )
    assert response.status_code == 400
    assert "时长必须是整数" in response.text


def test_non_finite_duration_is_400(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    session_id = start_session(c)
    page = c.get(f"/interview/session/{session_id}").text
    question_id = page.split('data-question-id="')[1].split('"')[0]
    c.put(f"/api/interview/session/{session_id}/answer",
          json={"question_id": question_id, "answer": "答案"})
    graded = c.post(
        f"/api/interview/session/{session_id}/grade",
        json={"question_id": question_id},
    ).json()
    payload = {
        "question_id": question_id,
        "scores": [
            {"dimension": item["dimension"], "score": 0.6}
            for item in graded["scores"]
        ],
        "duration_ms": 0,
    }
    # JSON has no Infinity literal; 1e400 parses to inf on the server.
    raw = json.dumps(payload).replace('"duration_ms": 0', '"duration_ms": 1e400')
    response = c.post(
        f"/api/interview/session/{session_id}/confirm",
        content=raw,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert "时长必须是整数" in response.text


class HugeScoreClient:
    """Return valid rubrics but with an integer too large for float()."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        dimensions = re.findall(r"^- (.+?)（权重", user, flags=re.MULTILINE)
        return json.dumps({
            "scores": [
                {"dimension": dimension, "score": int("9" * 400)}
                for dimension in dimensions
            ],
            "summary": "huge", "strengths": [], "gaps": [],
        }, ensure_ascii=False)


def test_grade_huge_integer_falls_back_to_manual(tmp_path: Path) -> None:
    client = HugeScoreClient()
    c = make_app(tmp_path, llm=client, config=CONFIG)
    session_id = start_session(c)
    page = c.get(f"/interview/session/{session_id}").text
    question_id = page.split('data-question-id="')[1].split('"')[0]
    c.put(f"/api/interview/session/{session_id}/answer",
          json={"question_id": question_id, "answer": "答案"})
    graded = c.post(
        f"/api/interview/session/{session_id}/grade",
        json={"question_id": question_id},
    )
    assert graded.status_code == 200
    assert graded.json()["mode"] == "manual"
    assert client.calls == 2


def test_confirm_huge_integer_score_is_400(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    session_id = start_session(c)
    page = c.get(f"/interview/session/{session_id}").text
    question_id = page.split('data-question-id="')[1].split('"')[0]
    c.put(f"/api/interview/session/{session_id}/answer",
          json={"question_id": question_id, "answer": "答案"})
    graded = c.post(
        f"/api/interview/session/{session_id}/grade",
        json={"question_id": question_id},
    ).json()
    response = c.post(
        f"/api/interview/session/{session_id}/confirm",
        json={
            "question_id": question_id,
            "scores": [
                {"dimension": item["dimension"], "score": int("9" * 400)}
                for item in graded["scores"]
            ],
            "duration_ms": 1000,
        },
    )
    assert response.status_code == 400


def test_cross_pack_session_is_not_listed_and_does_not_500(
    tmp_path: Path,
) -> None:
    db = tmp_path / "i.db"
    first = TestClient(create_app(
        SAMPLE, db, interview_banks=BANKS,
        interview_llm=FakeClient(), interview_config=CONFIG,
    ))
    session_id = start_session(first)
    ros2 = ROOT / "content-packs" / "ros2-qos"
    second = TestClient(create_app(
        ros2, db, interview_banks=BANKS,
        interview_llm=FakeClient(), interview_config=CONFIG,
    ))
    start_page = second.get("/interview")
    assert start_page.status_code == 200
    assert session_id not in start_page.text
    assert second.get(f"/interview/session/{session_id}").status_code == 404
    summary = second.get(f"/interview/session/{session_id}/summary")
    assert summary.status_code == 200
    assert "题目已不在题库中" in summary.text


def test_start_page_links_running_session_to_continue(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    session_id = start_session(c)
    page = c.get("/interview").text
    assert f'href="/interview/session/{session_id}"' in page
    assert "继续" in page
    assert "进行中" in page
    assert "running" in page


def test_abandoned_session_offers_no_continue(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    session_id = start_session(c)
    assert c.post(f"/api/interview/session/{session_id}/abandon",
                  json={}).status_code == 200
    summary = c.get(f"/interview/session/{session_id}/summary")
    assert summary.status_code == 200
    assert "继续作答" not in summary.text
    assert "已放弃" in summary.text
    page = c.get("/interview").text
    assert f'href="/interview/session/{session_id}/summary"' in page
    assert "已放弃" in page
