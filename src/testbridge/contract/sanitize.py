"""Allowlist-based HTML sanitization for lesson fragments."""

from __future__ import annotations

import re

import nh3

ALLOWED_TAGS = {
    "article", "section", "header", "footer", "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "ul", "ol", "li", "strong", "em", "code", "pre", "blockquote",
    "figure", "figcaption", "img", "svg", "g", "path", "circle", "rect",
    "line", "polyline", "polygon", "text", "tspan", "defs", "linearGradient",
    "stop", "table", "thead", "tbody", "tr", "th", "td", "a", "span", "div",
    "aside", "details", "summary", "br", "hr",
}

ALLOWED_ATTRIBUTES = {
    "*": {
        "class", "id", "data-tb-block", "data-tb-exercise", "data-tb-widget",
        "data-tb-resource", "data-variant", "data-language", "title",
    },
    # "rel" is omitted: nh3 >= 0.3 rejects listing it while link_rel is set.
    # link_rel already forces rel="noopener noreferrer" on every link.
    "a": {"href", "target"},
    "img": {"src", "alt", "width", "height"},
    "svg": {"viewBox", "viewbox", "xmlns", "width", "height", "fill", "stroke"},
    "path": {"d", "fill", "stroke", "stroke-width", "transform"},
    "circle": {"cx", "cy", "r", "fill", "stroke", "stroke-width", "transform"},
    "rect": {"x", "y", "width", "height", "rx", "fill", "stroke", "transform"},
    "line": {"x1", "y1", "x2", "y2", "stroke", "stroke-width", "transform"},
    "polyline": {"points", "fill", "stroke", "stroke-width", "transform"},
    "polygon": {"points", "fill", "stroke", "stroke-width", "transform"},
    "text": {"x", "y", "fill", "font-size", "text-anchor"},
    "tspan": {"x", "y", "fill"},
    "stop": {"offset", "stop-color", "stop-opacity"},
}

FORBIDDEN_TAG_RE = re.compile(
    r"<\s*(script|iframe|object|embed|form|input|button|textarea|select)\b",
    re.IGNORECASE,
)
EVENT_ATTR_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
STYLE_ATTR_RE = re.compile(r"\sstyle\s*=", re.IGNORECASE)
JS_URL_RE = re.compile(r"(?:href|src)\s*=\s*[\"']\s*javascript:", re.IGNORECASE)


def sanitize_fragment(html: str) -> str:
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
        strip_comments=True,
    )


def find_forbidden_html(html: str) -> list[str]:
    issues: list[str] = []
    for match in FORBIDDEN_TAG_RE.finditer(html):
        issues.append(f"forbidden tag: {match.group(1).lower()}")
    for match in EVENT_ATTR_RE.finditer(html):
        issues.append(f"forbidden event attribute: {match.group(0).strip()}")
    if STYLE_ATTR_RE.search(html):
        issues.append("forbidden inline style")
    if JS_URL_RE.search(html):
        issues.append("forbidden javascript: URL")
    return issues
