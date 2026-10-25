"""Search orchestration and research dossier.

The dossier is source evidence: it is written once per lesson and never edited
by the model in later steps.
"""

from __future__ import annotations

import html as html_lib
import json
from collections.abc import Callable
from dataclasses import dataclass, field

from testbridge.studio.outline import LessonPlan
from testbridge.studio.search import SearchHit, SearchProvider, trust_for
from testbridge.studio.store import DraftStore

SITE_QUERY = "site:docs.ros.org OR site:docs.ros2.org"
CONTENT_LIMIT = 4000


@dataclass(frozen=True)
class ResearchResult:
    lesson_id: str
    queries: list[str]
    hits: list[SearchHit]
    errors: list[str] = field(default_factory=list)
    searches: int = 0


def build_queries(
    lesson: LessonPlan, concept_titles: list[str], budget: int
) -> list[str]:
    queries = list(lesson.queries)
    queries.append(lesson.title)
    queries.append(f"{lesson.title} {SITE_QUERY}")
    queries.extend(concept_titles)
    seen: list[str] = []
    for query in queries:
        if query and query not in seen:
            seen.append(query)
    return seen[:max(1, budget)]


def run_research(
    lesson: LessonPlan,
    concept_titles: list[str],
    search: SearchProvider,
    budget: int,
    progress: Callable[[int, int, int], None] | None = None,
) -> ResearchResult:
    queries = build_queries(lesson, concept_titles, budget)
    hits: list[SearchHit] = []
    seen: set[str] = set()
    errors: list[str] = []
    for index, query in enumerate(queries, start=1):
        try:
            for hit in search.search(query, count=8):
                if hit.url in seen:
                    continue
                seen.add(hit.url)
                hits.append(hit)
        except Exception as exc:  # noqa: BLE001 - keep research going
            errors.append(f"{query}: {type(exc).__name__}")
        if progress is not None:
            progress(index, len(queries), len(hits))
    return ResearchResult(
        lesson_id=lesson.lesson_id, queries=queries, hits=hits,
        errors=errors, searches=len(queries),
    )


def render_research_html(lesson: LessonPlan, result: ResearchResult) -> str:
    rows = []
    for hit in result.hits:
        rows.append(
            f'<li class="tb-hit"><a href="{html_lib.escape(hit.url)}">'
            f"{html_lib.escape(hit.title or hit.url)}</a> "
            f'<span class="tb-trust">{trust_for(hit.authority)}</span>'
            f"<p>{html_lib.escape(hit.summary or hit.snippet)}</p></li>"
        )
    errors = "".join(
        f"<li>{html_lib.escape(item)}</li>" for item in result.errors
    )
    return (
        '<article class="tb-research">'
        f"<h1>调研档案：{html_lib.escape(lesson.title)}</h1>"
        f"<p>查询 {len(result.queries)} 次，命中 {len(result.hits)} 条。</p>"
        '<ul class="tb-queries">'
        + "".join(f"<li>{html_lib.escape(q)}</li>" for q in result.queries)
        + "</ul>"
        f'<ul class="tb-hits">{"".join(rows)}</ul>'
        + (f'<ul class="tb-errors">{errors}</ul>' if errors else "")
        + "</article>"
    )


def write_research(
    store: DraftStore,
    draft_id: str,
    lesson: LessonPlan,
    result: ResearchResult,
) -> None:
    payload = {
        "lesson_id": result.lesson_id,
        "queries": result.queries,
        "searches": result.searches,
        "errors": result.errors,
        "hits": [
            {
                "title": hit.title, "url": hit.url, "snippet": hit.snippet,
                "summary": hit.summary, "content": hit.content[:CONTENT_LIMIT],
                "authority": hit.authority, "date": hit.date,
                "trust": trust_for(hit.authority),
            }
            for hit in result.hits
        ],
    }
    store.write(
        draft_id, f"research/{result.lesson_id}.json",
        json.dumps(payload, ensure_ascii=False, indent=2),
    )
    store.write(
        draft_id, f"research/{result.lesson_id}.html",
        render_research_html(lesson, result),
    )
