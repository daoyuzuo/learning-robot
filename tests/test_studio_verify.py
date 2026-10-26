from testbridge.studio.verify import (
    MAX_BYTES,
    ResourceCheck,
    check_url,
    check_urls,
    reason,
    usable_urls,
)


class FakeResponse:
    def __init__(self, status: int, url: str = "", text: str = "", ctype: str = ""):
        self.status_code = status
        self.url = url
        self.text = text
        self.headers = {"content-type": ctype} if ctype else {}


class FakeClient:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses

    def get(self, url: str, **kwargs):
        return self.responses.get(url, FakeResponse(200, url, "x" * 2000))


def test_ok_page() -> None:
    client = FakeClient({"https://ok": FakeResponse(200, "https://ok", "x" * 2000)})
    check = check_url(client, "https://ok")
    assert check.ok is True
    assert check.status == 200


def test_http_error() -> None:
    client = FakeClient({"https://bad": FakeResponse(404, "https://bad", "no")})
    check = check_url(client, "https://bad")
    assert check.ok is False
    assert reason(check) == "HTTP 404"


def test_login_redirect_is_paywalled() -> None:
    client = FakeClient({
        "https://paper": FakeResponse(
            200, "https://publisher.example/login?next=/paper", "x" * 2000
        ),
    })
    check = check_url(client, "https://paper")
    assert check.paywalled is True
    assert check.ok is False


def test_paywall_phrase_is_flagged() -> None:
    client = FakeClient({
        "https://paper": FakeResponse(
            200, "https://paper", "Subscribe to continue reading. " + "x" * 2000
        ),
    })
    assert check_url(client, "https://paper").paywalled is True


def test_short_page_is_flagged() -> None:
    client = FakeClient({
        "https://thin": FakeResponse(200, "https://thin", "short", "text/html"),
    })
    assert check_url(client, "https://thin").paywalled is True


def test_forbidden_status_is_paywalled() -> None:
    client = FakeClient({"https://x": FakeResponse(403, "https://x", "x" * 2000)})
    assert check_url(client, "https://x").paywalled is True


def test_network_error_is_recorded() -> None:
    class Boom:
        def get(self, url: str, **kwargs):
            raise RuntimeError("boom")

    check = check_url(Boom(), "https://x")
    assert check.ok is False
    assert check.error == "RuntimeError"


def test_check_urls_respects_limit_and_dedupes() -> None:
    client = FakeClient({})
    checks = check_urls(client, ["https://a", "https://a", "https://b"], limit=2)
    assert set(checks) == {"https://a", "https://b"}
    assert usable_urls(checks) == {"https://a", "https://b"}


def test_check_round_trips_through_dict() -> None:
    check = ResourceCheck("https://x", 200, "https://x", 10, False, "")
    assert ResourceCheck.from_dict(check.as_dict()) == check


class StreamedResponse:
    """Context-managed response yielding a fixed list of chunks."""

    def __init__(self, chunks: list[bytes], status: int = 200,
                 url: str = "https://ok", ctype: str = "text/html") -> None:
        self.chunks = chunks
        self.status_code = status
        self.url = url
        self.headers = {"content-type": ctype}
        self.consumed = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def iter_bytes(self):
        for chunk in self.chunks:
            self.consumed += 1
            yield chunk


class StreamClient:
    def __init__(self, response: StreamedResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict]] = []

    def stream(self, method: str, url: str, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


def test_check_url_stops_reading_at_the_byte_cap() -> None:
    chunk = b"x" * 50_000
    response = StreamedResponse([chunk] * 6)
    client = StreamClient(response)

    check = check_url(client, "https://ok")

    # 200KB cap / 50KB chunks = 4 chunks consumed; the 5th and 6th are never
    # requested from the stream.
    assert response.consumed == MAX_BYTES // 50_000
    assert check.content_length == MAX_BYTES
    assert check.ok is True
    assert client.calls == [
        ("GET", "https://ok", {"follow_redirects": True}),
    ]
