import pytest

from testbridge.studio.search import SearchError, SearchHit
from testbridge.studio.search_router import (
    FallbackSearch,
    SearchRouter,
    is_academic,
)


def hit(url: str = "https://example.com/x") -> SearchHit:
    return SearchHit("t", url, "", "", "", 3)


class FakeSearch:
    def __init__(self, name: str, hits=None, error: bool = False) -> None:
        self.name = name
        self.hits = [] if hits is None else hits
        self.error = error
        self.queries: list[str] = []

    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        self.queries.append(query)
        if self.error:
            raise SearchError(f"{self.name} failed")
        return list(self.hits)

    def fetch(self, url: str) -> str:
        if self.error:
            raise SearchError(f"{self.name} failed")
        return self.name


def test_is_academic_keywords() -> None:
    assert is_academic("VLA 模型综述", [], []) is True
    assert is_academic("ROS 2 执行器", ["执行器"], ["ros2"]) is False
    assert is_academic("主题", ["Embodied AI"], []) is True
    assert is_academic("主题", [], ["research"]) is True
    assert is_academic("主题", [], ["robotics"]) is False


def test_manual_route() -> None:
    deepseek = FakeSearch("deepseek")
    router = SearchRouter({"deepseek": deepseek})

    route = router.route(
        "deepseek", topic="t", concept_titles=[], concept_domains=[]
    )

    assert route.name == "deepseek"
    assert route.provider is deepseek


def test_manual_missing_backend_raises() -> None:
    router = SearchRouter({"deepseek": FakeSearch("deepseek")})

    with pytest.raises(SearchError):
        router.route("openalex", topic="t", concept_titles=[], concept_domains=[])


def test_auto_academic_prefers_openalex() -> None:
    deepseek = FakeSearch("deepseek")
    openalex = FakeSearch("openalex", hits=[hit()])
    router = SearchRouter({"deepseek": deepseek, "openalex": openalex})

    route = router.route(
        "auto", topic="VLA 模型", concept_titles=[], concept_domains=[]
    )

    assert route.name == "auto:openalex->deepseek"
    assert route.provider.search("q") == [hit()]


def test_auto_docs_prefers_deepseek() -> None:
    deepseek = FakeSearch("deepseek", hits=[hit()])
    openalex = FakeSearch("openalex")
    router = SearchRouter({"deepseek": deepseek, "openalex": openalex})

    route = router.route(
        "auto", topic="ROS 2 执行器", concept_titles=[], concept_domains=["ros2"]
    )

    assert route.name == "auto:deepseek->openalex"
    assert route.provider.search("q")[0].url == "https://example.com/x"


def test_auto_with_single_provider_does_not_fallback() -> None:
    deepseek = FakeSearch("deepseek")
    router = SearchRouter({"deepseek": deepseek})

    route = router.route(
        "auto", topic="ROS 2", concept_titles=[], concept_domains=[]
    )

    assert route.name == "auto:deepseek"
    assert route.provider is deepseek


def test_auto_with_no_providers_raises() -> None:
    with pytest.raises(SearchError):
        SearchRouter({}).route(
            "auto", topic="t", concept_titles=[], concept_domains=[]
        )


def test_unknown_backend_treated_as_auto() -> None:
    deepseek = FakeSearch("deepseek")
    router = SearchRouter({"deepseek": deepseek})

    route = router.route(
        "bogus", topic="ROS 2", concept_titles=[], concept_domains=[]
    )

    assert route.name == "auto:deepseek"


def test_fallback_on_empty_result() -> None:
    primary = FakeSearch("primary")
    secondary = FakeSearch("secondary", hits=[hit()])

    assert FallbackSearch(primary, secondary).search("q") == [hit()]
    assert primary.queries == ["q"]
    assert secondary.queries == ["q"]


def test_fallback_on_primary_error() -> None:
    primary = FakeSearch("primary", error=True)
    secondary = FakeSearch("secondary", hits=[hit()])

    assert FallbackSearch(primary, secondary).search("q") == [hit()]


def test_fallback_both_fail() -> None:
    primary = FakeSearch("primary", error=True)
    secondary = FakeSearch("secondary", error=True)

    with pytest.raises(SearchError) as excinfo:
        FallbackSearch(primary, secondary).search("q")
    assert "primary" in str(excinfo.value)
    assert "secondary" in str(excinfo.value)


def test_fallback_fetch() -> None:
    primary = FakeSearch("primary")
    primary.fetch = lambda url: ""
    secondary = FakeSearch("secondary")

    assert FallbackSearch(primary, secondary).fetch("https://x") == "secondary"


def test_route_query_academic_uses_openalex() -> None:
    router = SearchRouter({
        "deepseek": FakeSearch("deepseek"),
        "openalex": FakeSearch("openalex"),
    })

    route = router.route_query(
        "auto", "academic", topic="t", concept_titles=[], concept_domains=[]
    )

    assert route.name == "auto:openalex->deepseek"


def test_route_query_engineering_uses_deepseek() -> None:
    router = SearchRouter({
        "deepseek": FakeSearch("deepseek"),
        "openalex": FakeSearch("openalex"),
    })

    route = router.route_query(
        "auto", "engineering", topic="t", concept_titles=[], concept_domains=[]
    )

    assert route.name == "auto:deepseek->openalex"


def test_route_query_manual_never_falls_back() -> None:
    router = SearchRouter({"deepseek": FakeSearch("deepseek")})

    route = router.route_query(
        "deepseek", "academic", topic="t", concept_titles=[], concept_domains=[]
    )

    assert route.name == "deepseek"
    assert isinstance(route.provider, FakeSearch)
