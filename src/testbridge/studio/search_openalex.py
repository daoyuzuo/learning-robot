"""OpenAlex works search adapter."""

from __future__ import annotations

import time
from typing import Any

import httpx

from testbridge.studio.search import SearchError, SearchHit

DEFAULT_BASE_URL = "https://api.openalex.org"
REVIEWED_TYPES = {"article", "review", "book-chapter", "proceedings-article"}
MAX_PER_PAGE = 50


def reconstruct_abstract(index: Any) -> str:
    if not isinstance(index, dict):
        return ""
    positions: dict[int, str] = {}
    for word, places in index.items():
        if not isinstance(places, list):
            continue
        for place in places:
            if isinstance(place, int) and place >= 0:
                positions[place] = str(word)
    if not positions:
        return ""
    return " ".join(positions[position] for position in sorted(positions))


def _doi_url(doi: Any) -> str:
    if not isinstance(doi, str) or not doi.strip():
        return ""
    value = doi.strip()
    if value.startswith(("http://", "https://")):
        return value
    if value.lower().startswith("doi:"):
        value = value[4:]
    return "https://doi.org/" + value


def _url_for(work: dict) -> str:
    doi_url = _doi_url(work.get("doi"))
    if doi_url:
        return doi_url
    primary = work.get("primary_location")
    if isinstance(primary, dict):
        landing = primary.get("landing_page_url")
        if isinstance(landing, str) and landing.startswith(("http://", "https://")):
            return landing
    open_access = work.get("open_access")
    if isinstance(open_access, dict):
        oa_url = open_access.get("oa_url")
        if isinstance(oa_url, str) and oa_url.startswith(("http://", "https://")):
            return oa_url
    work_id = work.get("id")
    if isinstance(work_id, str) and work_id.startswith(("http://", "https://")):
        return work_id
    return ""


def authority_for(work: dict) -> int:
    if work.get("is_retracted") is True:
        return -1
    work_type = str(work.get("type") or "").lower()
    if work_type in REVIEWED_TYPES:
        return 3
    if work_type == "preprint":
        return 2
    return 1


def _date_for(work: dict) -> str | None:
    date = work.get("publication_date")
    if isinstance(date, str) and date:
        return date
    year = work.get("publication_year")
    if isinstance(year, int):
        return f"{year}-01-01"
    return None


def _to_hit(work: dict) -> SearchHit | None:
    if not isinstance(work, dict):
        return None
    url = _url_for(work)
    if not url:
        return None
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    title = work.get("display_name") or work.get("title") or ""
    return SearchHit(
        title=str(title),
        url=url,
        snippet=abstract[:300],
        summary=abstract,
        content=abstract,
        authority=authority_for(work),
        date=_date_for(work),
    )


class OpenAlexSearch:
    def __init__(
        self,
        *,
        mailto: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        transport: httpx.BaseTransport | None = None,
        retry_delay: float = 1.0,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.mailto = mailto or None
        self.retry_delay = retry_delay
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def _request(self, params: dict) -> dict:
        last_error = "openalex request failed"
        for attempt in range(2):
            try:
                response = self._client.get(self.base_url + "/works", params=params)
                if response.status_code < 400:
                    try:
                        data = response.json()
                    except ValueError:
                        raise SearchError("openalex returned non-JSON") from None
                    return data if isinstance(data, dict) else {}
                last_error = f"openalex status {response.status_code}"
                if response.status_code != 429 and response.status_code < 500:
                    break
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                last_error = type(exc).__name__
            if attempt == 0 and self.retry_delay:
                time.sleep(self.retry_delay)
        raise SearchError(last_error)

    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        per_page = max(1, min(int(count), MAX_PER_PAGE))
        params: dict[str, Any] = {"search": query, "per-page": per_page}
        if self.mailto:
            params["mailto"] = self.mailto
        data = self._request(params)
        results = data.get("results")
        if not isinstance(results, list):
            return []
        hits = []
        for item in results:
            hit = _to_hit(item)
            if hit is not None:
                hits.append(hit)
        return hits[:per_page]

    def fetch(self, url: str) -> str:
        return ""
