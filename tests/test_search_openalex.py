import httpx
import pytest

from testbridge.studio.search import SearchError
from testbridge.studio.search_openalex import (
    OpenAlexSearch,
    authority_for,
    reconstruct_abstract,
)


def client(handler, **kwargs) -> OpenAlexSearch:
    return OpenAlexSearch(
        base_url="https://api.openalex.test",
        transport=httpx.MockTransport(handler),
        retry_delay=0,
        **kwargs,
    )


def work(**overrides) -> dict:
    base = {
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1000/x",
        "display_name": "Paper",
        "publication_date": "2025-01-02",
        "type": "article",
        "is_retracted": False,
        "abstract_inverted_index": {"hello": [0], "world": [1]},
        "primary_location": {"landing_page_url": "https://example.com/p"},
        "open_access": {"oa_url": "https://oa.example/p"},
    }
    base.update(overrides)
    return base


def test_reconstruct_abstract_orders_positions() -> None:
    assert reconstruct_abstract({"world": [1], "hello": [0]}) == "hello world"
    assert reconstruct_abstract({}) == ""
    assert reconstruct_abstract(None) == ""
    assert reconstruct_abstract({"x": "bad"}) == ""


def test_search_request_and_mapping() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"results": [work()]})

    hits = client(handler, mailto="me@example.com").search("robot", count=5)

    assert seen["params"]["search"] == "robot"
    assert seen["params"]["per-page"] == "5"
    assert seen["params"]["mailto"] == "me@example.com"
    assert hits[0].title == "Paper"
    assert hits[0].url == "https://doi.org/10.1000/x"
    assert hits[0].summary == "hello world"
    assert hits[0].snippet == "hello world"
    assert hits[0].authority == 3
    assert hits[0].date == "2025-01-02"


def test_publication_year_fallback() -> None:
    works = [
        work(publication_date=None, publication_year=2025),
        work(publication_date=None, publication_year=" 2024 "),
        work(publication_date=None, publication_year=True),
        work(publication_date=None),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": works})

    hits = client(handler).search("q")

    assert [hit.date for hit in hits] == ["2025", "2024", None, None]


def test_no_mailto_param_when_unset() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "mailto" not in request.url.params
        return httpx.Response(200, json={"results": []})

    assert client(handler).search("q") == []


def test_url_fallbacks_and_skip_without_url() -> None:
    works = [
        work(id="https://openalex.org/W2", doi=None,
             primary_location={"landing_page_url": "https://landing.example/p"},
             open_access={}),
        work(id="https://openalex.org/W3", doi=None,
             primary_location={}, open_access={"oa_url": "https://oa.example/p"}),
        work(id="https://openalex.org/W4", doi=None,
             primary_location={}, open_access={}),
        work(id=None, doi=None, primary_location={}, open_access={}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": works})

    hits = client(handler).search("q", count=10)

    assert [hit.url for hit in hits] == [
        "https://landing.example/p",
        "https://oa.example/p",
        "https://openalex.org/W4",
    ]


def test_authority_mapping() -> None:
    assert authority_for({"type": "article"}) == 3
    assert authority_for({"type": "review"}) == 3
    assert authority_for({"type": "preprint"}) == 2
    assert authority_for({"type": "dataset"}) == 1
    assert authority_for({"type": "article", "is_retracted": True}) == -1
    assert authority_for({}) == 1


def test_retracted_truthy_value_is_downgraded() -> None:
    assert authority_for({"type": "article", "is_retracted": 1}) == -1


def test_count_is_clamped_to_fifty() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["per-page"] = request.url.params["per-page"]
        return httpx.Response(200, json={"results": []})

    client(handler).search("q", count=100)

    assert seen["per-page"] == "50"


def test_count_zero_is_clamped_to_one() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["per-page"] = request.url.params["per-page"]
        return httpx.Response(200, json={"results": []})

    client(handler).search("q", count=0)

    assert seen["per-page"] == "1"


def test_retries_once_on_429() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={})
        return httpx.Response(200, json={"results": [work()]})

    assert client(handler).search("q")
    assert calls["n"] == 2


def test_retries_once_on_500() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={"results": [work()]})

    assert client(handler).search("q")
    assert calls["n"] == 2


def test_non_json_is_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    with pytest.raises(SearchError):
        client(handler).search("q")


def test_missing_results_returns_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    assert client(handler).search("q") == []


def test_client_error_does_not_retry() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={})

    with pytest.raises(SearchError):
        client(handler).search("q")
    assert calls["n"] == 1


def test_redirect_with_json_is_error() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(302, json={"results": [work()]})

    with pytest.raises(SearchError):
        client(handler).search("q")
    assert calls["n"] == 1


def test_fetch_returns_empty() -> None:
    assert client(lambda request: httpx.Response(200)).fetch("https://x") == ""
