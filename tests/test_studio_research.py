import json
from pathlib import Path

from testbridge.studio.outline import LessonPlan
from testbridge.studio.research import (
    ResearchResult,
    build_queries,
    classify_query,
    preflight_urls,
    render_research_for_prompt,
    render_research_html,
    run_research,
    usable_urls_from_payload,
    write_research,
)
from testbridge.studio.search import SearchHit
from testbridge.studio.search_router import SearchRouter
from testbridge.studio.store import DraftStore

LESSON = LessonPlan("L-1", "执行器", 20, ["目标"], ["ros executors"])


class FakeSearch:
    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.queries: list[str] = []

    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        self.queries.append(query)
        if query == self.fail_on:
            raise RuntimeError("boom")
        return [SearchHit(
            title="Executors", url=f"https://docs.ros.org/{query.replace(' ', '-')}",
            snippet="s", summary="summary", content="body", authority=3,
        )]

    def fetch(self, url: str) -> str:
        return ""


def test_build_queries_respects_budget_and_includes_site_query() -> None:
    queries = build_queries(LESSON, ["执行器基础", "回调组"], budget=4)
    texts = [item.text for item in queries]
    assert texts[0] == "ros executors"
    assert any("site:docs.ros.org" in item for item in texts)
    assert len(queries) <= 4
    assert {item.kind for item in queries} <= {"academic", "engineering", "official"}


def test_run_research_dedupes_by_url() -> None:
    result = run_research(LESSON, ["执行器基础"], FakeSearch(), budget=5)
    urls = [hit.url for hit in result.hits]
    assert len(urls) == len(set(urls))


def test_run_research_continues_after_failure() -> None:
    search = FakeSearch(fail_on="执行器基础")
    result = run_research(LESSON, ["执行器基础"], search, budget=5)
    assert result.errors
    assert result.hits


def test_write_research_creates_json_and_html(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id="demo", topic="t", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    result = run_research(LESSON, ["执行器基础"], FakeSearch(), budget=3)

    write_research(store, "demo", LESSON, result)

    assert (tmp_path / "drafts/demo/research/L-1.json").is_file()
    page = store.read("demo", "research/L-1.html")
    assert "docs.ros.org" in page
    assert "A" in page


def test_run_research_records_backend() -> None:
    result = run_research(
        LESSON, ["执行器基础"], FakeSearch(), budget=3, backend="openalex"
    )

    assert result.backend == "openalex"


def test_write_research_includes_backend(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id="demo", topic="t", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    result = run_research(
        LESSON, ["执行器基础"], FakeSearch(), budget=3, backend="deepseek"
    )

    write_research(store, "demo", LESSON, result)

    payload = json.loads(store.read("demo", "research/L-1.json"))
    assert payload["backend"] == "deepseek"


def test_research_html_escapes_titles() -> None:
    result = ResearchResult(
        lesson_id="L-1", queries=["q"], searches=1, errors=[],
        hits=[SearchHit("<script>", "https://x", "", "", "", 3)],
    )
    page = render_research_html(LESSON, result)
    assert "&lt;script&gt;" in page
    assert "<script>" not in page


def test_research_html_labels_hits_with_dossier_trust() -> None:
    hit = SearchHit("Executors", "https://docs.ros.org/x", "", "", "", 1)
    result = ResearchResult(
        lesson_id="L-1", queries=["q"], searches=1, errors=[], hits=[hit],
    )

    page = render_research_html(LESSON, result)

    # A whitelisted domain lifts authority-based C to B; the page must show the
    # same trust value that write_research stores in the dossier.
    assert '<span class="tb-trust">B</span>' in page


def test_build_queries_mixes_kinds() -> None:
    queries = build_queries(LESSON, ["执行器基础"], budget=8)
    kinds = {item.kind for item in queries}
    assert "engineering" in kinds
    assert "official" in kinds


def test_run_research_records_query_log() -> None:
    result = run_research(LESSON, ["执行器基础"], FakeSearch(), budget=3)

    assert result.query_log
    assert set(result.query_log[0]) == {"query", "kind", "backend"}


def test_run_research_uses_route_for_each_query() -> None:
    seen: list[str] = []
    deepseek = FakeSearch()
    openalex = FakeSearch()

    class RecordingRouter(SearchRouter):
        def route_query(self, backend, kind, **kwargs):
            seen.append(kind)
            return super().route_query(backend, kind, **kwargs)

    result = run_research(
        LESSON, ["执行器基础"], budget=3,
        route_for=lambda kind: RecordingRouter({
            "deepseek": deepseek, "openalex": openalex,
        }).route_query(
            "auto", kind, topic="t", concept_titles=[], concept_domains=[]
        ),
    )

    assert seen
    assert set(result.query_log[0]) == {"query", "kind", "backend"}


def test_write_research_records_kind_trust_and_check(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id="demo", topic="t", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    result = run_research(LESSON, ["执行器基础"], FakeSearch(), budget=1)

    class FakeCheck:
        def as_dict(self):
            return {"url": "https://x", "status": 200, "paywalled": False}

    checks = {hit.url: FakeCheck() for hit in result.hits}
    write_research(store, "demo", LESSON, result, checks=checks)

    payload = json.loads(store.read("demo", "research/L-1.json"))
    first = payload["hits"][0]
    assert first["kind"] in {
        "official_docs", "standard", "engineering_blog", "tutorial",
        "repository", "paper", "book", "video", "other",
    }
    assert first["trust"] in {"A", "B", "C", "D"}
    assert first["check"]["status"] == 200


def test_render_research_for_prompt_drops_unusable_hits() -> None:
    payload = json.dumps({
        "hits": [
            {"title": "ok", "url": "https://ok.example",
             "check": {"status": 200, "paywalled": False}},
            {"title": "wall", "url": "https://wall.example",
             "check": {"status": 200, "paywalled": True}},
            {"title": "404", "url": "https://gone.example",
             "check": {"status": 404, "paywalled": False}},
            {"title": "unchecked", "url": "https://unchecked.example"},
        ]
    })

    text = render_research_for_prompt(payload)

    assert "https://ok.example" in text
    assert "wall.example" not in text
    assert "gone.example" not in text
    # When any hit carries a check, unchecked hits are unusable too: the
    # lesson parser only accepts required URLs that were checked OK.
    assert "unchecked.example" not in text


def test_render_research_for_prompt_keeps_all_hits_without_checks() -> None:
    payload = json.dumps({
        "hits": [
            {"title": "a", "url": "https://a.example"},
            {"title": "b", "url": "https://b.example"},
        ]
    })

    text = render_research_for_prompt(payload)

    assert "https://a.example" in text
    assert "https://b.example" in text


def test_preflight_urls_keeps_one_hit_per_kind_within_limit() -> None:
    hits = [
        SearchHit("t1", "https://docs.example/tutorial/1", "", "", "", 2),
        SearchHit("t2", "https://docs.example/tutorial/2", "", "", "", 2),
        SearchHit("b1", "https://blog.example/posts/1", "", "", "", 2),
        SearchHit("b2", "https://blog.example/posts/2", "", "", "", 2),
        SearchHit("b3", "https://blog.example/posts/3", "", "", "", 2),
        SearchHit("o1", "https://other.example/1", "", "", "", 2),
        SearchHit("o2", "https://other.example/2", "", "", "", 2),
        SearchHit("official", "https://docs.ros.org/guide", "", "", "", 3),
    ]

    urls = preflight_urls(hits, limit=6)

    assert "https://docs.ros.org/guide" in urls
    assert len(urls) <= 6
    assert len(urls) == len(set(urls))
    # First pass covers each seen kind in first-seen order.
    assert urls[:4] == [
        "https://docs.example/tutorial/1",
        "https://blog.example/posts/1",
        "https://other.example/1",
        "https://docs.ros.org/guide",
    ]


def test_classify_query_matches_english_hints_on_word_boundaries() -> None:
    assert classify_query("inspect the executor") == "engineering"
    assert classify_query("user preference settings") == "engineering"
    assert classify_query("ROS 2 executor spec") == "official"
    assert classify_query("quick reference guide") == "official"
    assert classify_query("官方文档") == "official"


def test_write_research_persists_oa_triage_fields(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id="demo", topic="t", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    hit = SearchHit(
        "Paper", "https://doi.org/10.1/x", "", "", "", 3,
        is_oa=True, oa_url="https://repo.example/x.pdf", work_type="article",
    )
    result = ResearchResult(
        lesson_id="L-1", queries=["q"], searches=1, hits=[hit],
    )

    write_research(store, "demo", LESSON, result)

    payload = json.loads(store.read("demo", "research/L-1.json"))
    first = payload["hits"][0]
    assert first["is_oa"] is True
    assert first["oa_url"] == "https://repo.example/x.pdf"
    assert first["work_type"] == "article"


def test_usable_urls_from_payload() -> None:
    payload = json.dumps({
        "hits": [
            {"url": "https://ok.example",
             "check": {"status": 200, "paywalled": False}},
            {"url": "https://bad.example",
             "check": {"status": 404, "paywalled": False}},
        ]
    })

    assert usable_urls_from_payload(payload) == {"https://ok.example"}
    assert usable_urls_from_payload('{"hits": [{"url": "https://x"}]}') is None
    assert usable_urls_from_payload("not json") is None
