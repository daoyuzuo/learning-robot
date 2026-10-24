"""Allowlist-based HTML sanitization for lesson fragments."""

from __future__ import annotations

import re
from html.parser import HTMLParser

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
    "g": {"transform", "fill", "stroke", "stroke-width"},
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

FORBIDDEN_TAGS = frozenset(
    {
        "script", "iframe", "object", "embed", "form", "input", "button",
        "textarea", "select", "style", "link", "meta", "base",
    }
)
SAFE_URL_SCHEMES = frozenset({"http", "https", "mailto"})
RELATIVE_URL_PREFIXES = ("#", "/", "./", "../")
SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")


def _url_scheme(value: str) -> str | None:
    """Return a URL value's lowercased scheme, or None for relative URLs."""
    compact = "".join(
        ch for ch in value if not (ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F)
    )
    if not compact or compact.startswith(RELATIVE_URL_PREFIXES):
        return None
    match = SCHEME_RE.match(compact)
    return match.group(1).lower() if match else None


class _ForbiddenHTMLDetector(HTMLParser):
    """Collect issue descriptions from start tags; text nodes are ignored."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.issues: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect(tag, attrs)

    def _inspect(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower_tag = tag.lower()
        if lower_tag in FORBIDDEN_TAGS:
            self.issues.append(f"forbidden tag: {lower_tag}")
        for name, value in attrs:
            lower_name = name.lower()
            if lower_name.startswith("on"):
                self.issues.append(f"forbidden event attribute: {lower_name}")
            elif lower_name == "style":
                self.issues.append("forbidden inline style")
            elif lower_name in {"href", "src"} and value:
                scheme = _url_scheme(value)
                if scheme is not None and scheme not in SAFE_URL_SCHEMES:
                    self.issues.append(f"forbidden URL scheme: {scheme}")


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
    detector = _ForbiddenHTMLDetector()
    detector.feed(html)
    detector.close()
    return list(dict.fromkeys(detector.issues))
