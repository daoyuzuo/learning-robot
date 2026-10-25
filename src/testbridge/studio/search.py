"""DeepSeek Search & Fetch client.

Keys are read from :class:`TutorConfig` (environment only) and never appear in
error messages, logs, or on disk.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from testbridge.tutor.config import TutorConfig

TRUST_BY_AUTHORITY = {4: "A", 3: "A", 2: "B", 1: "C", 0: "D", -1: "D"}


def trust_for(authority: int) -> str:
    return TRUST_BY_AUTHORITY.get(authority, "D")


class SearchError(Exception):
    """The search or fetch request failed."""


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    summary: str
    content: str
    authority: int
    date: str | None = None


class SearchProvider(Protocol):
    def search(self, query: str, count: int = 10) -> list[SearchHit]: ...

    def fetch(self, url: str) -> str: ...


def _authority(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return -1


class DeepSeekSearch:
    def __init__(
        self,
        config: TutorConfig,
        transport: httpx.BaseTransport | None = None,
        retry_delay: float = 1.0,
    ) -> None:
        self.config = config
        self.retry_delay = retry_delay
        self._client = httpx.Client(timeout=config.timeout, transport=transport)

    def _post(self, path: str, payload: dict) -> dict:
        url = self.config.base_url.rstrip("/") + path
        last_error = "search failed"
        for attempt in range(2):
            try:
                response = self._client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                    json=payload,
                )
                if response.status_code < 400:
                    data = response.json()
                    return data if isinstance(data, dict) else {}
                last_error = f"upstream status {response.status_code}"
                if response.status_code != 429 and response.status_code < 500:
                    break
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                last_error = type(exc).__name__
            except ValueError:
                last_error = "upstream returned non-JSON"
            if attempt == 0 and self.retry_delay:
                time.sleep(self.retry_delay)
        raise SearchError(last_error)

    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        data = self._post(
            "/tools/search",
            {"query": query, "count": count, "need_content": True},
        )
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            return []
        hits = []
        for item in results:
            if not isinstance(item, dict) or not item.get("url"):
                continue
            date = item.get("date")
            hits.append(SearchHit(
                title=str(item.get("title") or ""),
                url=str(item["url"]),
                snippet=str(item.get("snippet") or ""),
                summary=str(item.get("summary") or ""),
                content=str(item.get("content") or ""),
                authority=_authority(item.get("authority")),
                date=date if isinstance(date, str) else None,
            ))
        return hits

    def fetch(self, url: str) -> str:
        data = self._post("/tools/fetch", {"url": url})
        return str(data.get("content") or "") if isinstance(data, dict) else ""
