import sqlite3
from pathlib import Path

import pytest

from testbridge.content.repository import load_pack
from testbridge.search import SearchError, SearchHit
from testbridge.tutor.client import TutorUpstreamError
from testbridge.tutor.config import TutorConfig
from testbridge.tutor.service import (
    InvalidQuestionError,
    LessonNotFoundError,
    TutorService,
)
from testbridge.tutor.store import TutorStore

PACK = load_pack(Path(__file__).parents[1] / "tests" / "fixtures" / "packs" / "ros2-qos")
CONFIG = TutorConfig(
    base_url="https://api.example.com/v1",
    api_key="sk-test",
    model="demo-model",
    timeout=5.0,
)
REPLY = (
    '{"answer": "因为订阅请求的可靠性更高。", "basis": "lesson", '
    '"citations": ["兼容性：Request vs Offered"], "followups": ["要不要试试？"]}'
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


class BrokenStore(TutorStore):
    def append(self, **kwargs):
        raise sqlite3.OperationalError("disk full")


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


def service(tmp_path: Path, client: FakeClient, store=None) -> TutorService:
    return TutorService(
        PACK, store or TutorStore(tmp_path / "t.db"), client, CONFIG
    )


def test_ask_returns_parsed_answer_and_persists_pair(tmp_path: Path) -> None:
    client = FakeClient()
    svc = service(tmp_path, client)

    reply = svc.ask("L-QOS-002", "兼容性：Request vs Offered", "为什么要求高就不连？")

    assert reply.saved is True
    assert reply.answer.basis == "lesson"
    assert reply.answer.citations == ["兼容性：Request vs Offered"]
    assert len(client.calls) == 1
    system, user = client.calls[0]
    assert "JSON" in system
    assert "重点解释：兼容性：Request vs Offered" in user
    assert "为什么要求高就不连？" in user
    assert "当前日期：" in user

    messages = svc.history("L-QOS-002")
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[1].basis == "lesson"


def test_unknown_lesson_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(LessonNotFoundError):
        service(tmp_path, FakeClient()).ask("L-NOPE", "", "问题")


def test_question_length_is_enforced(tmp_path: Path) -> None:
    svc = service(tmp_path, FakeClient())
    with pytest.raises(InvalidQuestionError):
        svc.ask("L-QOS-002", "", "   ")
    with pytest.raises(InvalidQuestionError):
        svc.ask("L-QOS-002", "", "字" * 501)


def test_unknown_anchor_is_ignored(tmp_path: Path) -> None:
    client = FakeClient()
    service(tmp_path, client).ask("L-QOS-002", "不存在的标题", "问题")
    assert "重点解释" not in client.calls[0][1]


def test_upstream_errors_propagate(tmp_path: Path) -> None:
    svc = service(tmp_path, FakeClient(error=TutorUpstreamError("boom")))
    with pytest.raises(TutorUpstreamError):
        svc.ask("L-QOS-002", "", "问题")


def test_store_failure_still_returns_answer(tmp_path: Path) -> None:
    svc = service(tmp_path, FakeClient(), store=BrokenStore(tmp_path / "t.db"))

    reply = svc.ask("L-QOS-002", "", "问题")

    assert reply.saved is False
    assert "订阅请求" in reply.answer.answer


def test_history_is_passed_back_and_capped(tmp_path: Path) -> None:
    client = FakeClient()
    svc = service(tmp_path, client)
    for index in range(6):
        svc.ask("L-QOS-002", "", f"问题{index}")

    svc.ask("L-QOS-002", "", "最后一问")

    prompt = client.calls[-1][1]
    assert "问题4" in prompt
    assert "问题0" not in prompt


def test_web_results_are_injected_and_cited(tmp_path: Path) -> None:
    hit = SearchHit(
        "外部依据", "https://example.com/a", "摘要", "摘要", "正文", 3
    )
    search = FakeSearch([hit])
    client = FakeClient(
        '{"answer": "x", "basis": "web", '
        '"citations": ["https://example.com/a"]}'
    )
    svc = TutorService(
        PACK, TutorStore(tmp_path / "t.db"), client, CONFIG, search=search
    )

    reply = svc.ask("L-QOS-002", "", "最新做法是什么？")

    assert reply.web_used is True
    assert search.calls
    assert "<web>" in client.calls[0][1]
    assert "https://example.com/a" in client.calls[0][1]
    assert reply.answer.basis == "web"
    assert reply.answer.citations == ["https://example.com/a"]


def test_search_failure_falls_back(tmp_path: Path) -> None:
    svc = TutorService(
        PACK, TutorStore(tmp_path / "t.db"), FakeClient(), CONFIG,
        search=BrokenSearch(),
    )

    reply = svc.ask("L-QOS-002", "", "问题")

    assert reply.web_used is False
    assert reply.answer.basis == "lesson"


def test_use_web_false_skips_search(tmp_path: Path) -> None:
    search = FakeSearch([])
    svc = TutorService(
        PACK, TutorStore(tmp_path / "t.db"), FakeClient(), CONFIG, search=search
    )

    svc.ask("L-QOS-002", "", "问题", use_web=False)

    assert search.calls == []


def test_web_hits_prefer_trusted_and_drop_d(tmp_path: Path) -> None:
    search = FakeSearch([
        SearchHit("C", "https://c.example", "", "", "c", 1),
        SearchHit("D", "https://d.example", "", "", "d", 0),
        SearchHit("B", "https://b.example", "", "", "b", 2),
        SearchHit("A", "https://a.example", "", "", "a", 4),
    ])
    svc = TutorService(
        PACK, TutorStore(tmp_path / "t.db"), FakeClient(), CONFIG, search=search
    )

    reply = svc.ask("L-QOS-002", "", "问题")

    assert [source["url"] for source in reply.web_sources] == [
        "https://a.example", "https://b.example", "https://c.example",
    ]
    assert [source["trust"] for source in reply.web_sources] == ["A", "B", "C"]
