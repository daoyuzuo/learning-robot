import httpx
import pytest

from testbridge.studio.search import DeepSeekSearch, SearchError, trust_for
from testbridge.tutor.config import TutorConfig

CONFIG = TutorConfig(
    base_url="https://api.example.com/v1", api_key="sk-test",
    model="deepseek-chat", timeout=5.0,
)


def client(handler) -> DeepSeekSearch:
    return DeepSeekSearch(CONFIG, transport=httpx.MockTransport(handler))


def test_trust_mapping() -> None:
    assert trust_for(4) == "A"
    assert trust_for(3) == "A"
    assert trust_for(2) == "B"
    assert trust_for(1) == "C"
    assert trust_for(0) == "D"
    assert trust_for(-1) == "D"


def test_search_posts_query_and_parses_hits() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"results": [{
            "title": "Executors", "url": "https://docs.ros.org/x",
            "snippet": "s", "summary": "sum", "content": "body",
            "authority": 3, "date": "2026-01-01T00:00:00+00:00",
        }]})

    hits = client(handler).search("ros executors", count=5)

    assert seen["url"] == "https://api.example.com/v1/tools/search"
    assert hits[0].url == "https://docs.ros.org/x"
    assert hits[0].authority == 3


def test_search_retries_once_then_fails() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, json={"error": "slow down"})

    with pytest.raises(SearchError):
        client(handler).search("q")
    assert calls["n"] == 2


def test_search_succeeds_after_one_retry() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={"results": []})

    assert client(handler).search("q") == []


def test_fetch_returns_markdown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/tools/fetch")
        return httpx.Response(200, json={"title": "t", "content": "# body"})

    assert client(handler).fetch("https://example.com") == "# body"


def test_error_does_not_leak_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={})

    with pytest.raises(SearchError) as excinfo:
        client(handler).search("q")
    assert "sk-test" not in str(excinfo.value)
