import httpx
import pytest

from testbridge.tutor.client import (
    OpenAICompatibleClient,
    TutorTimeoutError,
    TutorUpstreamError,
)
from testbridge.tutor.config import TutorConfig

CONFIG = TutorConfig(
    base_url="https://api.example.com/v1",
    api_key="sk-test",
    model="demo-model",
    timeout=5.0,
)


def client_with(handler) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        CONFIG, transport=httpx.MockTransport(handler), retry_delay=0.0
    )


def test_posts_chat_completion_and_returns_content() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )

    assert client_with(handler).complete("sys", "usr") == "ok"
    assert seen["url"] == "https://api.example.com/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"


def test_upstream_status_maps_to_error_without_key() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"error": "nope"})

    with pytest.raises(TutorUpstreamError) as excinfo:
        client_with(handler).complete("s", "u")
    assert "401" in str(excinfo.value)
    assert "sk-test" not in str(excinfo.value)
    assert calls == 1


def test_transient_status_is_retried_once() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(502, text="bad gateway")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )

    assert client_with(handler).complete("s", "u") == "ok"
    assert calls == 2


def test_rate_limit_is_retried_once() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, text="slow down")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )

    assert client_with(handler).complete("s", "u") == "ok"
    assert calls == 2


def test_transient_status_raises_after_two_attempts() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, text="unavailable")

    with pytest.raises(TutorUpstreamError) as excinfo:
        client_with(handler).complete("s", "u")
    assert "503" in str(excinfo.value)
    assert calls == 2


def test_timeout_is_retried_with_a_longer_deadline() -> None:
    calls = 0
    timeouts: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        timeout = request.extensions.get("timeout") or {}
        timeouts.append(float(timeout.get("read", 0)))
        if calls == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )

    assert client_with(handler).complete("s", "u") == "ok"
    assert calls == 2
    assert timeouts[1] >= timeouts[0] * 2


def test_empty_choices_is_upstream_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    with pytest.raises(TutorUpstreamError):
        client_with(handler).complete("s", "u")


def test_invalid_json_is_upstream_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    with pytest.raises(TutorUpstreamError):
        client_with(handler).complete("s", "u")


def test_timeout_maps_to_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    with pytest.raises(TutorTimeoutError):
        client_with(handler).complete("s", "u")
