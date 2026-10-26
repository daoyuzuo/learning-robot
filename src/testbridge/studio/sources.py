"""Deterministic source classification and trust floor for research hits.

The domain lists are author-layer rules: they are not written into content
packs and never take part in grading.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from testbridge.contract.models import ResourceKind
from testbridge.studio.search import SearchHit, trust_for

OFFICIAL_DOC_DOMAINS = frozenset({
    "docs.ros.org", "docs.ros2.org", "design.ros2.org",
    "docs.nvidia.com", "developer.nvidia.com", "docs.openvino.ai",
    "docs.python.org", "docs.docker.com", "kubernetes.io", "readthedocs.io",
})
STANDARD_DOMAINS = frozenset({
    "omg.org", "dds-foundation.org", "iso.org", "iec.ch", "nist.gov",
})
REPOSITORY_DOMAINS = frozenset({"github.com", "gitlab.com"})
PAPER_DOMAINS = frozenset({"doi.org", "arxiv.org", "openalex.org"})
VIDEO_DOMAINS = frozenset({"youtube.com", "youtu.be", "vimeo.com", "bilibili.com"})
PRACTICE_DOMAINS = frozenset({
    "discourse.ros.org", "ros.org", "openrobotics.org",
})
BLOG_DOMAINS = frozenset({"medium.com", "dev.to"})
TRUSTED_B_DOMAINS = (
    OFFICIAL_DOC_DOMAINS | STANDARD_DOMAINS | REPOSITORY_DOMAINS | PRACTICE_DOMAINS
)
PAPER_WORK_TYPES = frozenset({
    "article", "review", "book-chapter", "proceedings-article", "preprint",
    "dataset", "dissertation", "report",
})


def _host(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ""
    return (parts.hostname or "").lower()


def _path(url: str) -> str:
    try:
        return urlsplit(url.strip()).path.lower()
    except ValueError:
        return ""


def _matches(host: str, domains: frozenset[str]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def classify_url(url: str, *, work_type: str | None = None) -> ResourceKind:
    host = _host(url)
    if not host:
        return "other"
    kind = (work_type or "").strip().lower()
    if kind == "book":
        return "book"
    if kind in PAPER_WORK_TYPES:
        return "paper"
    if _matches(host, PAPER_DOMAINS):
        return "paper"
    if _matches(host, STANDARD_DOMAINS):
        return "standard"
    if _matches(host, VIDEO_DOMAINS):
        return "video"
    if _matches(host, OFFICIAL_DOC_DOMAINS):
        return "official_docs"
    if _matches(host, REPOSITORY_DOMAINS):
        path = _path(url)
        if "/docs" in path or "readme" in path:
            return "official_docs"
        return "repository"
    if _matches(host, BLOG_DOMAINS):
        return "engineering_blog"
    path = _path(url)
    if "/tutorial" in path or "/how-to" in path or "/getting-started" in path:
        return "tutorial"
    if "/blog" in path or "/posts/" in path or "/article" in path:
        return "engineering_blog"
    return "other"


def classify_hit(hit: SearchHit) -> ResourceKind:
    return classify_url(hit.url, work_type=hit.work_type)


def trust_for_hit(hit: SearchHit) -> str:
    """Base trust from authority, raised to B only for whitelisted domains."""
    base = trust_for(hit.authority)
    if base == "D":
        return "D"
    if base == "C" and _matches(_host(hit.url), TRUSTED_B_DOMAINS):
        return "B"
    return base
