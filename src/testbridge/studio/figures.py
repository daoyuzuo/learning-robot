"""Deterministic SVG figures rendered from a restricted JSON spec.

The model never writes SVG itself: it emits a small spec, and this module turns
it into inline SVG with escaped text and no scripts, styles, or external URLs.
"""

from __future__ import annotations

import html as html_lib
import math
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
MAX_FIGURES = 6
MAX_EDGES_FACTOR = 2
VIEWBOX_WIDTH = 800
LINE_HEIGHT = 18
BOX_HEIGHT = 64
ROW_HEIGHT = 2 * LINE_HEIGHT + 8
BOX_BOTTOM_PADDING = 10
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


def _list(value: object, *, field: str) -> list:
    if not isinstance(value, list):
        raise FigureError(f"{field} 必须是数组")
    return value


def _items(value: object, *, field: str) -> list:
    if not isinstance(value, list) or not (MIN_ITEMS <= len(value) <= MAX_ITEMS):
        raise FigureError(f"{field} 需要 {MIN_ITEMS}–{MAX_ITEMS} 项")
    return value


def _parse_flow(item: dict) -> dict:
    nodes = []
    seen = set()
    for raw in _list(item.get("nodes") or [], field="nodes"):
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
    raw_edges = _list(item.get("edges") or [], field="edges")
    if len(raw_edges) > MAX_EDGES_FACTOR * len(nodes):
        raise FigureError(f"edges 不能超过节点数的 {MAX_EDGES_FACTOR} 倍")
    edges = []
    for raw in raw_edges:
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
        items = _list(raw.get("items"), field="group.items")
        if not (1 <= len(items) <= MAX_GROUP_ITEMS):
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
    items = _list(value.get("items"), field=f"compare.{name}.items")
    if not (1 <= len(items) <= MAX_GROUP_ITEMS):
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
    if len(items) > MAX_FIGURES:
        raise FigureError(f"每课最多 {MAX_FIGURES} 张图")
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
        concepts = _list(raw.get("concepts") or [], field="figure.concepts")
        for concept_id in concepts:
            if not isinstance(concept_id, str):
                raise FigureError("figure.concepts 必须只含概念 id 字符串")
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


def _n(value: float) -> str:
    """Format an SVG coordinate with one decimal and no long float reprs."""
    return f"{value:.1f}"


def _units(text: str) -> int:
    return sum(2 if ord(char) >= 0x2E80 else 1 for char in text)


def _fit(px: float, size: int = 16) -> int:
    """How many half-width units fit in ``px`` at the given font size."""
    return max(2, int(px * 2 / size))


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


def _ellipsize(text: str, max_units: int) -> str:
    kept = ""
    for char in text:
        if _units(kept) + _units(char) + 1 > max_units:
            break
        kept += char
    return kept + "…"


def _text(
    x: float,
    y: float,
    text: str,
    max_units: int,
    *,
    size: int = 16,
    anchor: str = "middle",
    weight: int = 400,
    max_lines: int = 2,
) -> str:
    lines = _wrap(text, max_units)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _ellipsize(lines[-1], max_units)
    spans = "".join(
        f'<tspan x="{_n(x)}" dy="{0 if index == 0 else LINE_HEIGHT}">'
        f"{html_lib.escape(line)}</tspan>"
        for index, line in enumerate(lines)
    )
    return (
        f'<text x="{_n(x)}" y="{_n(y)}" font-size="{size}" font-weight="{weight}"'
        f' text-anchor="{anchor}" fill="currentColor">{spans}</text>'
    )


def _arrow(x1: float, y1: float, x2: float, y2: float) -> str:
    """Triangle whose tip sits on ``(x2, y2)`` and points along the edge."""
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return ""
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    px, py = -uy, ux
    back, half = 7.0, 4.5
    base_x, base_y = x2 - ux * back, y2 - uy * back
    left = (base_x + px * half, base_y + py * half)
    right = (base_x - px * half, base_y - py * half)
    return (
        f'<polygon points="{_n(x2)},{_n(y2)} {_n(left[0])},{_n(left[1])} '
        f'{_n(right[0])},{_n(right[1])}" fill="currentColor"/>'
    )


def _svg(width: int, height: float, spec: dict, body: str) -> str:
    return (
        f'<svg viewBox="0 0 {width} {_n(height)}" width="100%" role="img"'
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
    margin = 40.0
    box_h = BOX_HEIGHT
    positions: dict[str, tuple[float, float, float, float]] = {}
    if horizontal:
        # Shrink boxes when many nodes so two lines still fit without overlap.
        box_w = min(150.0, (VIEWBOX_WIDTH - 2 * margin) / count - 16)
        gap = (VIEWBOX_WIDTH - 2 * margin - count * box_w) / max(1, count - 1)
        height = 2 * margin + box_h + 36
        for index, node in enumerate(nodes):
            x = margin + index * (box_w + gap)
            positions[node["id"]] = (x, margin + 10, box_w, box_h)
    else:
        box_w = 280.0
        gap = 26.0
        height = 2 * margin + count * box_h + (count - 1) * gap
        for index, node in enumerate(nodes):
            x = (VIEWBOX_WIDTH - box_w) / 2
            y = margin + index * (box_h + gap)
            positions[node["id"]] = (x, y, box_w, box_h)
    label_units = _fit(box_w - 12)
    parts = []
    for node in nodes:
        x, y, w, h = positions[node["id"]]
        parts.append(
            f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" rx="8"'
            ' fill="currentColor" fill-opacity="0.06" stroke="currentColor"/>'
        )
        parts.append(_text(x + w / 2, y + h / 2 - 3, node["label"], label_units))
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
            f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}"'
            ' stroke="currentColor" stroke-width="1.5"/>'
        )
        parts.append(_arrow(x1, y1, x2, y2))
        if edge["label"]:
            if horizontal:
                units = _fit(max(16.0, x2 - x1 - 8), 12)
                parts.append(
                    _text(
                        (x1 + x2) / 2, (y1 + y2) / 2 - 8, edge["label"], units,
                        size=12, max_lines=1,
                    )
                )
            else:
                units = _fit(box_w - 16, 12)
                parts.append(
                    _text(
                        x1 + 8, (y1 + y2) / 2 + 4, edge["label"], units,
                        size=12, anchor="start", max_lines=1,
                    )
                )
    return _svg(VIEWBOX_WIDTH, height, spec, "".join(parts))


def _render_timeline(spec: dict) -> str:
    events = spec["events"]
    count = len(events)
    margin = 60.0
    step = (VIEWBOX_WIDTH - 2 * margin) / max(1, count - 1)
    axis_y = 105.0
    label_y = axis_y + 30
    detail_y = label_y + 2 * LINE_HEIGHT + 8
    height = detail_y + 2 * LINE_HEIGHT + 24
    label_units = _fit(step - 10)
    detail_units = _fit(step - 10, 12)
    parts = [
        (
            f'<line x1="{_n(margin)}" y1="{_n(axis_y)}"'
            f' x2="{_n(VIEWBOX_WIDTH - margin)}" y2="{_n(axis_y)}"'
            ' stroke="currentColor" stroke-width="2"/>'
        )
    ]
    for index, event in enumerate(events):
        x = margin + index * step
        # Endpoints only have half the interior spacing between them and the
        # viewBox edge, so grow their labels outward instead of centering them.
        if index == 0:
            anchor = "start"
        elif index == count - 1:
            anchor = "end"
        else:
            anchor = "middle"
        parts.append(
            f'<circle cx="{_n(x)}" cy="{_n(axis_y)}" r="6" fill="currentColor"/>'
        )
        parts.append(
            _text(x, axis_y - 22, event["at"], label_units, size=13, weight=600,
                  anchor=anchor, max_lines=1)
        )
        parts.append(
            _text(x, label_y, event["label"], label_units, anchor=anchor)
        )
        if event["detail"]:
            parts.append(_text(x, detail_y, event["detail"], detail_units, size=12,
                               anchor=anchor))
    return _svg(VIEWBOX_WIDTH, height, spec, "".join(parts))


def _render_block(spec: dict) -> str:
    groups = spec["groups"]
    count = len(groups)
    gap = 20.0
    margin = 30.0
    width = (VIEWBOX_WIDTH - 2 * margin - (count - 1) * gap) / count
    box_top = 30.0
    title_y = box_top + 28
    item_y = title_y + 2 * LINE_HEIGHT + 12
    rows = max(len(group["items"]) for group in groups)
    height = item_y + (rows - 1) * ROW_HEIGHT + 2 * LINE_HEIGHT + 24
    box_height = height - box_top - BOX_BOTTOM_PADDING
    title_units = _fit(width - 12)
    item_units = _fit(width - 12, 13)
    parts = []
    for index, group in enumerate(groups):
        x = margin + index * (width + gap)
        parts.append(
            f'<rect x="{_n(x)}" y="{_n(box_top)}" width="{_n(width)}"'
            f' height="{_n(box_height)}" rx="10"'
            ' fill="currentColor" fill-opacity="0.05" stroke="currentColor"/>'
        )
        parts.append(_text(x + width / 2, title_y, group["label"], title_units,
                           weight=600))
        for row, item in enumerate(group["items"]):
            parts.append(
                _text(x + width / 2, item_y + row * ROW_HEIGHT, item, item_units,
                      size=13)
            )
    return _svg(VIEWBOX_WIDTH, height, spec, "".join(parts))


def _render_compare(spec: dict) -> str:
    columns = (("left", 30.0), ("right", 420.0))
    col_w = 350.0
    box_top = 30.0
    title_y = box_top + 32
    item_y = title_y + 2 * LINE_HEIGHT + 12
    rows = max(len(spec["left"]["items"]), len(spec["right"]["items"]))
    height = item_y + (rows - 1) * ROW_HEIGHT + 2 * LINE_HEIGHT + 24
    box_height = height - box_top - BOX_BOTTOM_PADDING
    title_units = _fit(col_w - 24)
    item_units = _fit(col_w - 24, 13)
    parts = []
    for key, x in columns:
        side = spec[key]
        parts.append(
            f'<rect x="{_n(x)}" y="{_n(box_top)}" width="{_n(col_w)}"'
            f' height="{_n(box_height)}" rx="10"'
            ' fill="currentColor" fill-opacity="0.05" stroke="currentColor"/>'
        )
        parts.append(_text(x + col_w / 2, title_y, side["title"], title_units,
                           weight=600))
        for row, item in enumerate(side["items"]):
            parts.append(
                _text(x + col_w / 2, item_y + row * ROW_HEIGHT, item, item_units,
                      size=13)
            )
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
        figure = rendered.get(figure_id)
        if figure is None:
            raise FigureError(f"挂载点无法解析：{figure_id}")
        replaced.append(figure_id)
        return figure

    result = MOUNT_RE.sub(replace, html)
    if len(replaced) != len(scanner.mounts):
        raise FigureError("挂载点必须为空：<div data-tb-figure=\"FIG-1\"></div>")
    return result
