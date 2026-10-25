import json
from pathlib import Path

from testbridge.studio.outline import LessonPlan
from testbridge.studio.research import (
    ResearchResult,
    build_queries,
    render_research_html,
    run_research,
    write_research,
)
from testbridge.studio.search import SearchHit
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
    assert queries[0] == "ros executors"
    assert any("site:docs.ros.org" in item for item in queries)
    assert len(queries) <= 4


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
