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
from testbridge.studio.search import SearchHit, SearchProvider
from testbridge.studio.search_router import ACADEMIC_KEYWORDS, SearchRoute
from testbridge.studio.sources import classify_hit, trust_for_hit
from testbridge.studio.store import DraftStore

SITE_QUERY = "site:docs.ros.org OR site:docs.ros2.org"
CONTENT_LIMIT = 4000
QUERY_KINDS = ("academic", "engineering", "official")
OFFICIAL_HINTS = (
    "site:", "docs.", "documentation", "官方文档", "标准", "spec", "reference",
)


@dataclass(frozen=True)
class ResearchQuery:
    text: str
    kind: str


@dataclass(frozen=True)
class ResearchResult:
    lesson_id: str
    queries: list[str]
    hits: list[SearchHit]
    errors: list[str] = field(default_factory=list)
    searches: int = 0
    backend: str = ""
    query_log: list[dict] = field(default_factory=list)


def classify_query(text: str) -> str:
    lowered = text.lower()
    if any(hint in lowered for hint in ACADEMIC_KEYWORDS):
        return "academic"
    if any(hint in lowered for hint in OFFICIAL_HINTS):
        return "official"
    return "engineering"


def build_queries(
    lesson: LessonPlan, concept_titles: list[str], budget: int
) -> list[ResearchQuery]:
    candidates = [
        *lesson.queries, lesson.title,
        f"{lesson.title} {SITE_QUERY}", *concept_titles,
    ]
    buckets: dict[str, list[ResearchQuery]] = {kind: [] for kind in QUERY_KINDS}
    seen: set[str] = set()
    for text in candidates:
        if not text or text in seen:
            continue
        seen.add(text)
        kind = classify_query(text)
        buckets[kind].append(ResearchQuery(text, kind))
    limit = max(1, budget)
    ordered: list[ResearchQuery] = []
    while len(ordered) < limit and any(buckets.values()):
        for kind in QUERY_KINDS:
            if len(ordered) >= limit:
                break
            if buckets[kind]:
                ordered.append(buckets[kind].pop(0))
    return ordered


def run_research(
    lesson: LessonPlan,
    concept_titles: list[str],
    search: SearchProvider | None = None,
    budget: int = 1,
    progress: Callable[[int, int, int], None] | None = None,
    backend: str = "",
    *,
    route_for: Callable[[str], SearchRoute] | None = None,
) -> ResearchResult:
    queries = build_queries(lesson, concept_titles, budget)
    hits: list[SearchHit] = []
    seen: set[str] = set()
    errors: list[str] = []
    names: list[str] = []
    query_log: list[dict] = []
    for index, query in enumerate(queries, start=1):
        if route_for is not None:
            route = route_for(query.kind)
            provider = route.provider
            name = route.name
        elif search is not None:
            provider = search
            name = backend
        else:
            raise TypeError("run_research requires search= or route_for=")
        names.append(name)
        try:
            for hit in provider.search(query.text, count=8):
                if hit.url in seen:
                    continue
                seen.add(hit.url)
                hits.append(hit)
        except Exception as exc:  # noqa: BLE001 - keep research going
            errors.append(f"{query.text}: {type(exc).__name__}")
        query_log.append(
            {"query": query.text, "kind": query.kind, "backend": name}
        )
        if progress is not None:
            progress(index, len(queries), len(hits))
    resolved_backend = backend or ",".join(dict.fromkeys(names))
    return ResearchResult(
        lesson_id=lesson.lesson_id,
        queries=[item.text for item in queries],
        hits=hits,
        errors=errors,
        searches=len(queries),
        backend=resolved_backend,
        query_log=query_log,
    )


def render_research_html(lesson: LessonPlan, result: ResearchResult) -> str:
    rows = []
    for hit in result.hits:
        rows.append(
            f'<li class="tb-hit"><a href="{html_lib.escape(hit.url)}">'
            f"{html_lib.escape(hit.title or hit.url)}</a> "
            f'<span class="tb-trust">{trust_for_hit(hit)}</span> '
            f'<span class="tb-kind">{classify_hit(hit)}</span>'
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
    *,
    checks: dict | None = None,
) -> None:
    hits = []
    for hit in result.hits:
        item = {
            "title": hit.title, "url": hit.url, "snippet": hit.snippet,
            "summary": hit.summary, "content": hit.content[:CONTENT_LIMIT],
            "authority": hit.authority, "date": hit.date,
            "trust": trust_for_hit(hit),
            "kind": classify_hit(hit),
        }
        check = checks.get(hit.url) if checks else None
        if check is not None:
            item["check"] = check.as_dict()
        hits.append(item)
    payload = {
        "lesson_id": result.lesson_id,
        "queries": result.queries,
        "searches": result.searches,
        "backend": result.backend,
        "errors": result.errors,
        "query_log": result.query_log,
        "hits": hits,
    }
    store.write(
        draft_id, f"research/{result.lesson_id}.json",
        json.dumps(payload, ensure_ascii=False, indent=2),
    )
    store.write(
        draft_id, f"research/{result.lesson_id}.html",
        render_research_html(lesson, result),
    )


def _check_ok(check: dict) -> bool:
    status = check.get("status")
    return (
        not check.get("error")
        and isinstance(status, int)
        and status < 400
        and not check.get("paywalled")
    )


def render_research_for_prompt(payload: str) -> str:
    try:
        data = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    lines = []
    for hit in data.get("hits") or []:
        if not isinstance(hit, dict):
            continue
        check = hit.get("check")
        if isinstance(check, dict) and not _check_ok(check):
            continue
        lines.append(json.dumps({
            key: hit.get(key)
            for key in (
                "title", "url", "summary", "content",
                "authority", "trust", "kind", "check",
            )
        }, ensure_ascii=False))
    return "\n".join(lines)


def usable_urls_from_payload(payload: str) -> set[str] | None:
    try:
        data = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    hits = [hit for hit in data.get("hits") or [] if isinstance(hit, dict)]
    if not any(isinstance(hit.get("check"), dict) for hit in hits):
        return None
    return {
        str(hit.get("url") or "")
        for hit in hits
        if isinstance(hit.get("check"), dict) and _check_ok(hit["check"])
    }
