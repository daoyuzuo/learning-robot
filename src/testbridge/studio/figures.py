"""Deterministic SVG figures rendered from a restricted JSON spec.

The model never writes SVG itself: it emits a small spec, and this module turns
it into inline SVG with escaped text and no scripts, styles, or external URLs.
"""

from __future__ import annotations

import html as html_lib
import re
from html.parser import HTMLParser

FIGURE_KINDS = ("flow", "timeline", "block", "compare")
LABEL_LIMIT = 40
DETAIL_LIMIT = 80
CAPTION_LIMIT = 200
MIN_ITEMS = 2
MAX_ITEMS = 8
MAX_GROUPS = 4
MAX_GROUP_ITEMS = 5
VIEWBOX_WIDTH = 800
LINE_HEIGHT = 18
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")
MOUNT_RE = re.compile(
    r'<div\b[^>]*\bdata-tb-figure\s*=\s*(["\'])([^"\']+)\1[^>]*>\s*</div>',
    re.IGNORECASE,
)


class FigureError(Exception):
    """A figure spec or its mount point is invalid."""


def _str(value: object, limit: int, *, field: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise FigureError(f"{field} 必须是字符串")
    text = value.strip()
    if not text and not allow_empty:
        raise FigureError(f"{field} 不能为空")
    if len(text) > limit:
        raise FigureError(f"{field} 超过 {limit} 字")
    return text


def _items(value: object, *, field: str) -> list:
    if not isinstance(value, list) or not (MIN_ITEMS <= len(value) <= MAX_ITEMS):
        raise FigureError(f"{field} 需要 {MIN_ITEMS}–{MAX_ITEMS} 项")
    return value


def _parse_flow(item: dict) -> dict:
    nodes = []
    seen = set()
    for raw in item.get("nodes") or []:
        if not isinstance(raw, dict):
            raise FigureError("flow.node 必须是对象")
        node_id = _str(raw.get("id"), LABEL_LIMIT, field="node.id")
        if not ID_RE.fullmatch(node_id):
            raise FigureError(f"node.id 非法：{node_id}")
        if node_id in seen:
            raise FigureError(f"node.id 重复：{node_id}")
        seen.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "label": _str(raw.get("label"), LABEL_LIMIT, field="node.label"),
            }
        )
    if not (MIN_ITEMS <= len(nodes) <= MAX_ITEMS):
        raise FigureError(f"flow 需要 {MIN_ITEMS}–{MAX_ITEMS} 个节点")
    edges = []
    for raw in item.get("edges") or []:
        if not isinstance(raw, dict):
            raise FigureError("flow.edge 必须是对象")
        source = _str(raw.get("from"), LABEL_LIMIT, field="edge.from")
        target = _str(raw.get("to"), LABEL_LIMIT, field="edge.to")
        if source not in seen or target not in seen:
            raise FigureError("edge 引用了未声明的节点")
        label = _str(
            raw.get("label", ""), LABEL_LIMIT, field="edge.label", allow_empty=True
        )
        edges.append({"from": source, "to": target, "label": label})
    direction = str(item.get("direction") or "LR").upper()
    if direction not in {"LR", "TB"}:
        raise FigureError("direction 只能是 LR 或 TB")
    return {"nodes": nodes, "edges": edges, "direction": direction}


def _parse_timeline(item: dict) -> dict:
    events = []
    for raw in _items(item.get("events"), field="events"):
        if not isinstance(raw, dict):
            raise FigureError("timeline.event 必须是对象")
        events.append(
            {
                "at": _str(raw.get("at"), LABEL_LIMIT, field="event.at"),
                "label": _str(raw.get("label"), LABEL_LIMIT, field="event.label"),
                "detail": _str(
                    raw.get("detail", ""),
                    DETAIL_LIMIT,
                    field="event.detail",
                    allow_empty=True,
                ),
            }
        )
    return {"events": events}


def _parse_block(item: dict) -> dict:
    groups = item.get("groups")
    if not isinstance(groups, list) or not (1 <= len(groups) <= MAX_GROUPS):
        raise FigureError(f"groups 需要 1–{MAX_GROUPS} 组")
    parsed = []
    for raw in groups:
        if not isinstance(raw, dict):
            raise FigureError("block.group 必须是对象")
        items = raw.get("items")
        if not isinstance(items, list) or not (1 <= len(items) <= MAX_GROUP_ITEMS):
            raise FigureError(f"group.items 需要 1–{MAX_GROUP_ITEMS} 项")
        parsed.append(
            {
                "label": _str(raw.get("label"), LABEL_LIMIT, field="group.label"),
                "items": [
                    _str(value, LABEL_LIMIT, field="group.item") for value in items
                ],
            }
        )
    return {"groups": parsed}


def _parse_compare_side(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise FigureError(f"compare.{name} 必须是对象")
    items = value.get("items")
    if not isinstance(items, list) or not (1 <= len(items) <= MAX_GROUP_ITEMS):
        raise FigureError(f"compare.{name}.items 需要 1–{MAX_GROUP_ITEMS} 项")
    return {
        "title": _str(value.get("title"), LABEL_LIMIT, field=f"compare.{name}.title"),
        "items": [
            _str(item, LABEL_LIMIT, field=f"compare.{name}.item") for item in items
        ],
    }


def _parse_compare(item: dict) -> dict:
    return {
        "left": _parse_compare_side(item.get("left"), "left"),
        "right": _parse_compare_side(item.get("right"), "right"),
    }


_PARSERS = {
    "flow": _parse_flow,
    "timeline": _parse_timeline,
    "block": _parse_block,
    "compare": _parse_compare,
}


def parse_figures(items: object, concept_ids: set[str]) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise FigureError("figures 必须是数组")
    figures = []
    seen: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise FigureError("figure 必须是对象")
        figure_id = _str(raw.get("id"), LABEL_LIMIT, field="figure.id")
        if not ID_RE.fullmatch(figure_id):
            raise FigureError(f"figure.id 非法：{figure_id}")
        if figure_id in seen:
            raise FigureError(f"figure.id 重复：{figure_id}")
        kind = str(raw.get("kind") or "").strip().lower()
        if kind not in _PARSERS:
            raise FigureError(f"不支持的 figure.kind：{kind}")
        concepts = raw.get("concepts") or []
        if not isinstance(concepts, list):
            raise FigureError("figure.concepts 必须是数组")
        for concept_id in concepts:
            if concept_id not in concept_ids:
                raise FigureError(f"figure 引用了不存在的概念：{concept_id}")
        parsed = {
            "id": figure_id,
            "kind": kind,
            "caption": _str(raw.get("caption"), CAPTION_LIMIT, field="figure.caption"),
            "alt": _str(raw.get("alt"), CAPTION_LIMIT, field="figure.alt"),
            "title": _str(
                raw.get("title", ""), CAPTION_LIMIT, field="figure.title",
                allow_empty=True,
            ),
            "concepts": list(concepts),
        }
        parsed.update(_PARSERS[kind](raw))
        figures.append(parsed)
        seen.add(figure_id)
    return figures


def _wrap(text: str, max_units: int) -> list[str]:
    lines: list[str] = []
    current = ""
    width = 0
    for char in text:
        step = 2 if ord(char) >= 0x2E80 else 1
        if current and width + step > max_units:
            lines.append(current)
            current, width = "", 0
        current += char
        width += step
    if current:
        lines.append(current)
    return lines or [""]


def _text(
    x: float,
    y: float,
    text: str,
    max_units: int,
    *,
    size: int = 16,
    anchor: str = "middle",
    weight: int = 400,
) -> str:
    lines = _wrap(text, max_units)[:4]
    spans = "".join(
        f'<tspan x="{x}" dy="{0 if index == 0 else LINE_HEIGHT}">'
        f"{html_lib.escape(line)}</tspan>"
        for index, line in enumerate(lines)
    )
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}"'
        f' text-anchor="{anchor}" fill="currentColor">{spans}</text>'
    )


def _svg(width: int, height: int, spec: dict, body: str) -> str:
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img"'
        ' xmlns="http://www.w3.org/2000/svg">'
        f"<title>{html_lib.escape(spec['caption'])}</title>"
        f"<desc>{html_lib.escape(spec['alt'])}</desc>"
        f"{body}</svg>"
    )


def _render_flow(spec: dict) -> str:
    nodes = spec["nodes"]
    edges = spec["edges"]
    horizontal = spec["direction"] == "LR"
    count = len(nodes)
    positions: dict[str, tuple[float, float, float, float]] = {}
    if horizontal:
        box_h, margin = 64, 40
        # Shrink boxes when many nodes so they still fit inside the viewBox.
        box_w = min(150, (VIEWBOX_WIDTH - 2 * margin) / count - 16)
        gap = (VIEWBOX_WIDTH - 2 * margin - count * box_w) / max(1, count - 1)
        height = 180
        for index, node in enumerate(nodes):
            x = margin + index * (box_w + gap)
            positions[node["id"]] = (x, 50, box_w, box_h)
    else:
        box_w, box_h, margin = 280, 56, 40
        gap = 26
        height = 2 * margin + count * box_h + (count - 1) * gap
        for index, node in enumerate(nodes):
            x = (VIEWBOX_WIDTH - box_w) / 2
            y = margin + index * (box_h + gap)
            positions[node["id"]] = (x, y, box_w, box_h)
    parts = []
    for node in nodes:
        x, y, w, h = positions[node["id"]]
        parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8"'
            ' fill="currentColor" fill-opacity="0.06" stroke="currentColor"/>'
        )
        parts.append(_text(x + w / 2, y + h / 2 + 5, node["label"], int(w / 9)))
    for edge in edges:
        sx, sy, sw, sh = positions[edge["from"]]
        tx, ty, tw, th = positions[edge["to"]]
        if horizontal:
            x1, y1 = sx + sw, sy + sh / 2
            x2, y2 = tx, ty + th / 2
        else:
            x1, y1 = sx + sw / 2, sy + sh
            x2, y2 = tx + tw / 2, ty
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"'
            ' stroke="currentColor" stroke-width="1.5"/>'
        )
        angle = 6
        parts.append(
            f'<polygon points="{x2},{y2} {x2 - angle},{y2 - angle} '
            f'{x2 - angle},{y2 + angle}" fill="currentColor"/>'
        )
        if edge["label"]:
            parts.append(
                _text((x1 + x2) / 2, (y1 + y2) / 2 - 8, edge["label"], 12, size=12)
            )
    return _svg(VIEWBOX_WIDTH, int(height), spec, "".join(parts))


def _render_timeline(spec: dict) -> str:
    events = spec["events"]
    count = len(events)
    margin = 60
    step = (VIEWBOX_WIDTH - 2 * margin) / max(1, count - 1)
    y = 105
    parts = [
        (
            f'<line x1="{margin}" y1="{y}" x2="{VIEWBOX_WIDTH - margin}" y2="{y}"'
            ' stroke="currentColor" stroke-width="2"/>'
        )
    ]
    for index, event in enumerate(events):
        x = margin + index * step
        parts.append(f'<circle cx="{x}" cy="{y}" r="6" fill="currentColor"/>')
        parts.append(_text(x, y - 22, event["at"], 14, size=13, weight=600))
        parts.append(_text(x, y + 34, event["label"], 16))
        if event["detail"]:
            parts.append(_text(x, y + 56, event["detail"], 20, size=12))
    return _svg(VIEWBOX_WIDTH, 190, spec, "".join(parts))


def _render_block(spec: dict) -> str:
    groups = spec["groups"]
    count = len(groups)
    gap = 20
    margin = 30
    width = (VIEWBOX_WIDTH - 2 * margin - (count - 1) * gap) / count
    height = 210
    parts = []
    for index, group in enumerate(groups):
        x = margin + index * (width + gap)
        parts.append(
            f'<rect x="{x}" y="30" width="{width}" height="{height - 40}" rx="10"'
            ' fill="currentColor" fill-opacity="0.05" stroke="currentColor"/>'
        )
        parts.append(
            _text(x + width / 2, 58, group["label"], int(width / 9), weight=600)
        )
        for row, item in enumerate(group["items"]):
            parts.append(
                _text(x + width / 2, 92 + row * 24, item, int(width / 9), size=13)
            )
    return _svg(VIEWBOX_WIDTH, height, spec, "".join(parts))


def _render_compare(spec: dict) -> str:
    columns = (("left", 30), ("right", 420))
    height = 220
    parts = []
    for key, x in columns:
        side = spec[key]
        parts.append(
            f'<rect x="{x}" y="30" width="350" height="{height - 50}" rx="10"'
            ' fill="currentColor" fill-opacity="0.05" stroke="currentColor"/>'
        )
        parts.append(_text(x + 175, 62, side["title"], 32, weight=600))
        for row, item in enumerate(side["items"]):
            parts.append(_text(x + 175, 98 + row * 24, item, 32, size=13))
    return _svg(VIEWBOX_WIDTH, height, spec, "".join(parts))


_RENDERERS = {
    "flow": _render_flow,
    "timeline": _render_timeline,
    "block": _render_block,
    "compare": _render_compare,
}


def render_figure(spec: dict) -> str:
    return _RENDERERS[spec["kind"]](spec)


class _MountScanner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.mounts: list[tuple[str, bool]] = []

    def handle_starttag(self, tag, attrs):
        lower = tag.lower()
        if lower == "article":
            self.depth += 1
        names = {name.lower(): value for name, value in attrs}
        if lower == "div" and names.get("data-tb-figure"):
            self.mounts.append((str(names["data-tb-figure"]), self.depth > 0))

    def handle_startendtag(self, tag, attrs):
        # A self-closing tag opens no scope, so <article/> must not raise depth.
        names = {name.lower(): value for name, value in attrs}
        if tag.lower() == "div" and names.get("data-tb-figure"):
            self.mounts.append((str(names["data-tb-figure"]), self.depth > 0))

    def handle_endtag(self, tag):
        if tag.lower() == "article" and self.depth:
            self.depth -= 1


def embed_figures(html: str, figures: list[dict]) -> str:
    scanner = _MountScanner()
    scanner.feed(html)
    scanner.close()
    specs = {figure["id"]: figure for figure in figures}
    counts: dict[str, int] = {}
    for figure_id, inside in scanner.mounts:
        if not inside:
            raise FigureError(f"挂载点 {figure_id} 不在 <article> 内")
        counts[figure_id] = counts.get(figure_id, 0) + 1
        if counts[figure_id] > 1:
            raise FigureError(f"挂载点重复：{figure_id}")
        if figure_id not in specs:
            raise FigureError(f"挂载点没有对应规格：{figure_id}")
    for figure_id in specs:
        if figure_id not in counts:
            raise FigureError(f"图形缺少挂载点：{figure_id}")
    rendered = {
        figure_id: (
            '<figure class="tb-figure">'
            + render_figure(spec)
            + f"<figcaption>{html_lib.escape(spec['caption'])}</figcaption></figure>"
        )
        for figure_id, spec in specs.items()
    }
    replaced: list[str] = []

    def replace(match: re.Match) -> str:
        figure_id = match.group(2)
        replaced.append(figure_id)
        return rendered[figure_id]

    result = MOUNT_RE.sub(replace, html)
    if len(replaced) != len(scanner.mounts):
        raise FigureError("挂载点必须为空：<div data-tb-figure=\"FIG-1\"></div>")
    return result
