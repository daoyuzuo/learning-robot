"""Reachability and paywall checks for lesson resources.

Detection only: the module never tries to bypass a wall and never pretends a
resource was reachable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

MIN_CONTENT_LENGTH = 800
MAX_BYTES = 200_000
PAYWALL_STATUS = frozenset({401, 402, 403})
PAYWALL_PATH = re.compile(
    r"(log-?in|sign-?in|sign-?up|subscribe|purchase|paywall|register)", re.I
)
PAYWALL_PHRASES = (
    "subscribe to continue", "purchase this", "access denied",
    "sign in to continue", "already a subscriber",
)


@dataclass(frozen=True)
class ResourceCheck:
    url: str
    status: int | None
    final_url: str
    content_length: int
    paywalled: bool
    error: str = ""

    @property
    def ok(self) -> bool:
        return (
            not self.error
            and self.status is not None
            and self.status < 400
            and not self.paywalled
        )

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "status": self.status,
            "final_url": self.final_url,
            "content_length": self.content_length,
            "paywalled": self.paywalled,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResourceCheck":
        return cls(
            url=str(data.get("url") or ""),
            status=data.get("status"),
            final_url=str(data.get("final_url") or ""),
            content_length=int(data.get("content_length") or 0),
            paywalled=bool(data.get("paywalled")),
            error=str(data.get("error") or ""),
        )


def _paywalled(status: int, final_url: str, text: str, ctype: str) -> bool:
    if status in PAYWALL_STATUS:
        return True
    try:
        path = urlsplit(final_url).path or ""
    except ValueError:
        path = ""
    if PAYWALL_PATH.search(path):
        return True
    lowered = text.lower()
    if any(phrase in lowered for phrase in PAYWALL_PHRASES):
        return True
    if text and "html" in ctype and len(text) < MIN_CONTENT_LENGTH:
        return True
    return False


def check_url(client, url: str) -> ResourceCheck:
    try:
        response = client.get(url, follow_redirects=True)
    except Exception as exc:  # noqa: BLE001 - any transport error is a failure
        return ResourceCheck(url, None, url, 0, False, type(exc).__name__)
    status = int(getattr(response, "status_code", 0) or 0)
    final_url = str(getattr(response, "url", "") or url)
    text = str(getattr(response, "text", "") or "")[:MAX_BYTES]
    headers = getattr(response, "headers", {}) or {}
    ctype = str(headers.get("content-type", "") or "").lower()
    return ResourceCheck(
        url=url,
        status=status,
        final_url=final_url,
        content_length=len(text),
        paywalled=_paywalled(status, final_url, text, ctype),
        error="",
    )


def check_urls(client, urls, *, limit: int = 10) -> dict[str, ResourceCheck]:
    checks: dict[str, ResourceCheck] = {}
    for url in urls:
        if not url or url in checks:
            continue
        if len(checks) >= limit:
            break
        checks[url] = check_url(client, url)
    return checks


def usable_urls(checks: dict[str, ResourceCheck]) -> set[str]:
    return {url for url, check in checks.items() if check.ok}


def reason(check: ResourceCheck) -> str:
    if check.error:
        return check.error
    if check.status is not None and check.status >= 400:
        return f"HTTP {check.status}"
    if check.paywalled:
        return "paywalled"
    return "unreachable"
