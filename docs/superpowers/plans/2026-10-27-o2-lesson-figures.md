# O2 课程图文并茂（确定性 SVG）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Studio 生成的每节课能带 1–2 张离线、确定性、无版权风险的内联 SVG 思路图（流程/时间线/分组/对比），并让缺图与未解析挂载点在质量检查里可见。

**Architecture:** 模型只输出受限 JSON 图形规格；`studio/figures.py` 负责解析、确定性 SVG 渲染与挂载点替换；`parse_lesson_json` 在净化前后各做一次安全检查；质量层新增图示覆盖 warning 与未解析挂载点硬错误；`tb/1` 契约不变，图直接内联在课程 HTML 里。

**Tech Stack:** Python 3.10+、标准库 `html` / `html.parser` / `re`、nh3 净化器、pytest。

**Spec:** `docs/superpowers/specs/2026-10-26-o2-lesson-figures-design.md`

## Global Constraints

- 不改 `tb/1` 内容契约；不新增内容文件；图全部内联 SVG。
- 模型不得直接输出 `<svg>` 或外部 `<img>`；只接受受限 JSON 规格。
- 不接外部图片、不接 AI 生图、不新增依赖。
- 净化器只扩白名单（`title` / `desc` / `role` / aria 属性 / `font-weight` / `fill-opacity` 等），**不得**放行 `style`、`script`、`on*`、外部 URL。
- 所有文字用 `currentColor`，兼容深色模式；不使用 `<style>`、外部字体。
- 规格错误、挂载点缺失/重复/多余 → `LessonError`，由既有 `generate()` 重试一次，不静默删图。
- 默认 `pytest` 全绿且不联网；`tb validate` 两个现有包 0/0；已发布包 `tb quality` 分数不下降。
- prompt 版本升到 `studio/4`；旧草稿保持 `studio/1`–`studio/3`，不自动迁移。
- 标识符/注释英文；面向用户文案中文。

---

## File Structure

- Modify: `src/testbridge/contract/sanitize.py` — 白名单扩展。
- Create: `src/testbridge/studio/figures.py` — 规格解析、SVG 渲染、挂载替换。
- Modify: `src/testbridge/studio/lessons.py` — 解析 figures、嵌入、危险 HTML 拒绝。
- Modify: `src/testbridge/studio/prompts.py` — 图形要求与输出格式。
- Modify: `src/testbridge/studio/version.py` — `studio/4`。
- Modify: `src/testbridge/quality/evaluate.py` — 合并图示检查。
- Create: `src/testbridge/quality/figures.py` — 缺图 warning / 未解析挂载点 error。
- Modify: `web/studio.py` — 写课步骤记录 `figure_count`。
- Modify: `docs/ROADMAP.md`、`docs/OPTIMIZATION.md`、O2 spec 状态。
- Tests: `tests/test_studio_figures.py`、`tests/test_quality_figures.py`（新建），`tests/test_studio_lessons.py`、`tests/test_sanitize.py`、`tests/test_studio_prompts.py`、`tests/test_studio_version.py`（补充）。

---

### Task 1: 净化器白名单 + 图形渲染模块

**Files:**
- Modify: `src/testbridge/contract/sanitize.py`
- Create: `src/testbridge/studio/figures.py`
- Test: `tests/test_studio_figures.py` (create)、`tests/test_sanitize.py` (append)

**Interfaces:**
- Produces:
  - `figures.FigureError(Exception)`
  - `figures.FIGURE_KINDS: tuple[str, ...]`
  - `figures.parse_figures(items: object, concept_ids: set[str]) -> list[dict]`
  - `figures.render_figure(spec: dict) -> str`
  - `figures.embed_figures(html: str, figures: list[dict]) -> str`
  - `sanitize_fragment` 保留 `svg/title/desc/role/aria-*` 以及渲染用属性。

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_studio_figures.py
import pytest

from testbridge.studio.figures import (
    FigureError,
    embed_figures,
    parse_figures,
    render_figure,
)

FLOW = {
    "id": "FIG-1", "kind": "flow", "caption": "测试链路",
    "alt": "采集到判定的三步流程",
    "nodes": [{"id": "n1", "label": "采集"}, {"id": "n2", "label": "回放"}],
    "edges": [{"from": "n1", "to": "n2", "label": "数据"}],
}
TIMELINE = {
    "id": "FIG-2", "kind": "timeline", "caption": "时间线", "alt": "三段时序",
    "events": [{"at": "t0", "label": "发送"}, {"at": "t1", "label": "接收", "detail": "含延迟"}],
}
BLOCK = {
    "id": "FIG-3", "kind": "block", "caption": "模块", "alt": "两组模块",
    "groups": [
        {"label": "感知", "items": ["相机", "IMU"]},
        {"label": "判定", "items": ["规则", "模型"]},
    ],
}
COMPARE = {
    "id": "FIG-4", "kind": "compare", "caption": "对比", "alt": "仿真与实车对比",
    "left": {"title": "仿真", "items": ["可重复", "成本低"]},
    "right": {"title": "实车", "items": ["真实噪声", "成本高"]},
}


def test_parse_accepts_all_four_kinds() -> None:
    parsed = parse_figures([FLOW, TIMELINE, BLOCK, COMPARE], {"c"})
    assert [item["kind"] for item in parsed] == ["flow", "timeline", "block", "compare"]


def test_parse_rejects_duplicate_id() -> None:
    with pytest.raises(FigureError):
        parse_figures([FLOW, {**TIMELINE, "id": "FIG-1"}], {"c"})


def test_parse_rejects_unknown_kind() -> None:
    with pytest.raises(FigureError):
        parse_figures([{**FLOW, "kind": "pie"}], {"c"})


def test_parse_rejects_missing_caption_or_alt() -> None:
    for field in ("caption", "alt"):
        broken = {**FLOW, field: ""}
        with pytest.raises(FigureError):
            parse_figures([broken], {"c"})


def test_parse_rejects_overlong_label() -> None:
    broken = {
        **FLOW,
        "nodes": [{"id": "n1", "label": "长" * 41}, {"id": "n2", "label": "回放"}],
    }
    with pytest.raises(FigureError):
        parse_figures([broken], {"c"})


def test_parse_rejects_unknown_concept() -> None:
    with pytest.raises(FigureError):
        parse_figures([{**FLOW, "concepts": ["other"]}], {"c"})


def test_parse_rejects_edge_to_unknown_node() -> None:
    broken = {**FLOW, "edges": [{"from": "n1", "to": "n9"}]}
    with pytest.raises(FigureError):
        parse_figures([broken], {"c"})


def test_parse_rejects_too_few_nodes() -> None:
    broken = {**FLOW, "nodes": [{"id": "n1", "label": "采集"}], "edges": []}
    with pytest.raises(FigureError):
        parse_figures([broken], {"c"})


def test_parse_rejects_too_many_groups() -> None:
    broken = {
        **BLOCK,
        "groups": [{"label": f"g{i}", "items": ["x"]} for i in range(5)],
    }
    with pytest.raises(FigureError):
        parse_figures([broken], {"c"})


@pytest.mark.parametrize("spec", [FLOW, TIMELINE, BLOCK, COMPARE])
def test_render_contains_accessible_svg(spec) -> None:
    svg = render_figure(parse_figures([spec], {"c"})[0])
    assert svg.startswith("<svg ")
    assert "<title>" in svg and "<desc>" in svg
    assert 'role="img"' in svg
    assert 'width="100%"' in svg
    assert "currentColor" in svg
    assert "<script" not in svg and "style=" not in svg


def test_render_keeps_chinese_labels() -> None:
    svg = render_figure(parse_figures([FLOW], {"c"})[0])
    assert "采集" in svg
    assert "数据" in svg


def test_embed_replaces_mount_with_figure() -> None:
    html = '<article class="tb-lesson"><p>x</p><div data-tb-figure="FIG-1"></div></article>'
    out = embed_figures(html, parse_figures([FLOW], {"c"}))
    assert "data-tb-figure" not in out
    assert '<figure class="tb-figure">' in out
    assert "<figcaption>测试链路</figcaption>" in out


def test_embed_rejects_missing_mount() -> None:
    html = '<article class="tb-lesson"><p>x</p></article>'
    with pytest.raises(FigureError):
        embed_figures(html, parse_figures([FLOW], {"c"}))


def test_embed_rejects_duplicate_mount() -> None:
    mount = '<div data-tb-figure="FIG-1"></div>'
    html = f'<article class="tb-lesson">{mount}{mount}</article>'
    with pytest.raises(FigureError):
        embed_figures(html, parse_figures([FLOW], {"c"}))


def test_embed_rejects_orphan_spec() -> None:
    mount = '<div data-tb-figure="FIG-2"></div>'
    html = f'<article class="tb-lesson">{mount}</article>'
    with pytest.raises(FigureError):
        embed_figures(html, parse_figures([FLOW], {"c"}))


def test_embed_rejects_mount_outside_article() -> None:
    html = '<article class="tb-lesson"><p>x</p></article><div data-tb-figure="FIG-1"></div>'
    with pytest.raises(FigureError):
        embed_figures(html, parse_figures([FLOW], {"c"}))
```

```python
# append to tests/test_sanitize.py
def test_svg_accessibility_attributes_survive() -> None:
    html = (
        '<figure class="tb-figure"><svg viewBox="0 0 10 10" role="img" '
        'aria-label="图"><title>标题</title><desc>说明</desc>'
        '<text x="1" y="2" font-weight="600" fill-opacity="0.5">字</text>'
        "</svg><figcaption>说明</figcaption></figure>"
    )
    clean = sanitize_fragment(html)
    assert "<title>标题</title>" in clean
    assert "<desc>说明</desc>" in clean
    assert 'role="img"' in clean
    assert 'aria-label="图"' in clean
    assert 'font-weight="600"' in clean
    assert 'fill-opacity="0.5"' in clean


def test_svg_still_drops_scripts_and_styles() -> None:
    html = '<svg onload="x()" style="color:red"><script>1</script></svg>'
    clean = sanitize_fragment(html)
    assert "onload" not in clean
    assert "style=" not in clean
    assert "<script" not in clean
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_studio_figures.py tests/test_sanitize.py -v`
Expected: FAIL — `ModuleNotFoundError: testbridge.studio.figures`；净化器丢弃 `title/desc/role`。

- [ ] **Step 3: Write minimal implementation**

`src/testbridge/contract/sanitize.py`：

```python
ALLOWED_TAGS = {
    "article", "section", "header", "footer", "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "ul", "ol", "li", "strong", "em", "code", "pre", "blockquote",
    "figure", "figcaption", "img", "svg", "g", "path", "circle", "rect",
    "line", "polyline", "polygon", "text", "tspan", "defs", "linearGradient",
    "stop", "title", "desc",
    "table", "thead", "tbody", "tr", "th", "td", "a", "span", "div",
    "aside", "details", "summary", "br", "hr",
}

ALLOWED_ATTRIBUTES = {
    "*": {
        "class", "id", "data-tb-block", "data-tb-exercise", "data-tb-widget",
        "data-tb-resource", "data-tb-figure", "data-variant", "data-language",
        "title", "role", "aria-label", "aria-describedby", "aria-hidden",
        "focusable",
    },
    "a": {"href", "target"},
    "img": {"src", "alt", "width", "height"},
    "svg": {"viewBox", "viewbox", "xmlns", "width", "height", "fill", "stroke"},
    "g": {"transform", "fill", "stroke", "stroke-width", "fill-opacity", "stroke-opacity"},
    "path": {"d", "fill", "stroke", "stroke-width", "transform", "fill-opacity", "stroke-opacity"},
    "circle": {"cx", "cy", "r", "fill", "stroke", "stroke-width", "transform", "fill-opacity"},
    "rect": {"x", "y", "width", "height", "rx", "fill", "stroke", "transform", "fill-opacity", "stroke-opacity"},
    "line": {"x1", "y1", "x2", "y2", "stroke", "stroke-width", "transform", "stroke-opacity"},
    "polyline": {"points", "fill", "stroke", "stroke-width", "transform"},
    "polygon": {"points", "fill", "stroke", "stroke-width", "transform", "fill-opacity"},
    "text": {"x", "y", "fill", "font-size", "text-anchor", "font-weight", "fill-opacity"},
    "tspan": {"x", "y", "dy", "fill", "font-weight", "fill-opacity"},
    "stop": {"offset", "stop-color", "stop-opacity"},
}
```

`src/testbridge/studio/figures.py`（完整实现）：

```python
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
        nodes.append({"id": node_id, "label": _str(raw.get("label"), LABEL_LIMIT, field="node.label")})
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
        label = _str(raw.get("label", ""), LABEL_LIMIT, field="edge.label", allow_empty=True)
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
        events.append({
            "at": _str(raw.get("at"), LABEL_LIMIT, field="event.at"),
            "label": _str(raw.get("label"), LABEL_LIMIT, field="event.label"),
            "detail": _str(raw.get("detail", ""), DETAIL_LIMIT, field="event.detail", allow_empty=True),
        })
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
        parsed.append({
            "label": _str(raw.get("label"), LABEL_LIMIT, field="group.label"),
            "items": [_str(value, LABEL_LIMIT, field="group.item") for value in items],
        })
    return {"groups": parsed}


def _parse_compare_side(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise FigureError(f"compare.{name} 必须是对象")
    items = value.get("items")
    if not isinstance(items, list) or not (1 <= len(items) <= MAX_GROUP_ITEMS):
        raise FigureError(f"compare.{name}.items 需要 1–{MAX_GROUP_ITEMS} 项")
    return {
        "title": _str(value.get("title"), LABEL_LIMIT, field=f"compare.{name}.title"),
        "items": [_str(item, LABEL_LIMIT, field=f"compare.{name}.item") for item in items],
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
            "title": _str(raw.get("title", ""), CAPTION_LIMIT, field="figure.title", allow_empty=True),
            "concepts": list(concepts),
        }
        parsed.update(_PARSERS[kind](raw))
        figures.append(parsed)
        seen.add(figure_id)
    return figures
```

渲染部分（同一文件，接在解析之后）：

```python
def _units(text: str) -> int:
    return sum(2 if ord(char) >= 0x2E80 else 1 for char in text)


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
    x: float, y: float, text: str, max_units: int, *,
    size: int = 16, anchor: str = "middle", weight: int = 400,
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
        box_w, box_h, margin = 150, 64, 40
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
        f'<line x1="{margin}" y1="{y}" x2="{VIEWBOX_WIDTH - margin}" y2="{y}"'
        ' stroke="currentColor" stroke-width="2"/>'
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
        parts.append(_text(x + width / 2, 58, group["label"], int(width / 9), weight=600))
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
```

挂载替换：

```python
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
    def replace(match: re.Match) -> str:
        return rendered[match.group(2)]
    return MOUNT_RE.sub(replace, html)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_studio_figures.py tests/test_sanitize.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/contract/sanitize.py src/testbridge/studio/figures.py \
  tests/test_studio_figures.py tests/test_sanitize.py
git commit -m "feat: render deterministic svg figures from a spec"
```

---

### Task 2: 写课集成、prompt `studio/4`、Web 记录

**Files:**
- Modify: `src/testbridge/studio/lessons.py`
- Modify: `src/testbridge/studio/prompts.py`
- Modify: `src/testbridge/studio/version.py`
- Modify: `web/studio.py`
- Test: `tests/test_studio_lessons.py`, `tests/test_studio_prompts.py`, `tests/test_studio_version.py`

**Interfaces:**
- Consumes: `figures.parse_figures` / `embed_figures` / `FigureError`（Task 1）。
- Produces:
  - `LessonOutput.figures: list[dict]`
  - `parse_lesson_json` 接受 `figures`，并拒绝正文中的 `<svg>` 与外部 `<img>`。
  - `PROMPT_VERSION == "studio/4"`。

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_studio_lessons.py
FIGURE = {
    "id": "FIG-1", "kind": "flow", "caption": "测试链路",
    "alt": "采集到判定的两步流程",
    "nodes": [{"id": "n1", "label": "采集"}, {"id": "n2", "label": "判定"}],
    "edges": [{"from": "n1", "to": "n2"}],
}


def _payload_with_figure(*, html: str | None = None, figures=None) -> str:
    body = html or (
        '<article class="tb-lesson"><h1>课</h1>'
        '<div data-tb-exercise="EX-1"></div>'
        '<div data-tb-figure="FIG-1"></div></article>'
    )
    return json.dumps({
        **PAYLOAD, "html": body, "figures": [FIGURE] if figures is None else figures,
    })


def test_lesson_embeds_inline_svg() -> None:
    output = parse_lesson_json(
        _payload_with_figure(), LESSON, {"executor-basics"}
    )
    assert output.figures[0]["id"] == "FIG-1"
    assert '<figure class="tb-figure">' in output.html
    assert "<svg " in output.html
    assert 'data-tb-figure="FIG-1"' not in output.html


def test_lesson_rejects_missing_mount() -> None:
    body = '<article class="tb-lesson"><div data-tb-exercise="EX-1"></div></article>'
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload_with_figure(html=body), LESSON, {"executor-basics"}
        )


def test_lesson_rejects_direct_svg() -> None:
    body = (
        '<article class="tb-lesson"><div data-tb-exercise="EX-1"></div>'
        '<svg viewBox="0 0 1 1"></svg></article>'
    )
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload_with_figure(html=body, figures=[]),
            LESSON, {"executor-basics"},
        )


def test_lesson_rejects_external_image() -> None:
    body = (
        '<article class="tb-lesson"><div data-tb-exercise="EX-1"></div>'
        '<img src="https://example.com/x.png" alt="x"></article>'
    )
    with pytest.raises(LessonError):
        parse_lesson_json(
            _payload_with_figure(html=body, figures=[]),
            LESSON, {"executor-basics"},
        )


def test_lesson_without_figures_still_works() -> None:
    output = parse_lesson_json(
        json.dumps({**PAYLOAD, "figures": []}), LESSON, {"executor-basics"}
    )
    assert output.figures == []
```

```python
# append to tests/test_studio_prompts.py
def test_lesson_prompt_requires_figures() -> None:
    assert "figures" in LESSON_SYSTEM
    assert "data-tb-figure" in LESSON_SYSTEM
    assert "caption" in LESSON_SYSTEM and "alt" in LESSON_SYSTEM
```

`tests/test_studio_version.py`：`assert PROMPT_VERSION == "studio/4"`。

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_studio_lessons.py tests/test_studio_prompts.py tests/test_studio_version.py -v`
Expected: FAIL — `LessonOutput` 无 `figures`，prompt 无图形要求，版本仍是 `studio/3`。

- [ ] **Step 3: Write minimal implementation**

`src/testbridge/studio/lessons.py`：

```python
from testbridge.studio.figures import FigureError, embed_figures, parse_figures
```

`LessonOutput` 增加字段：

```python
@dataclass(frozen=True)
class LessonOutput:
    manifest: dict
    html: str
    exercises: list[dict] = field(default_factory=list)
    resources: list[dict] = field(default_factory=list)
    figures: list[dict] = field(default_factory=list)
```

`parse_lesson_json` 中，HTML 安全检查与图形处理：

```python
    if re.search(r"<\s*svg", html, re.IGNORECASE):
        raise LessonError("正文不得直接包含 SVG，请使用 figures 规格")
    if re.search(
        r'<img\b[^>]*\bsrc\s*=\s*["\']https?://', html, re.IGNORECASE
    ):
        raise LessonError("正文不得引用外部图片")
    clean = sanitize_fragment(html)
    if "<article" not in clean:
        raise LessonError("正文净化后为空")
    try:
        figures = parse_figures(data.get("figures") or [], concept_ids)
        clean = embed_figures(clean, figures)
    except FigureError as exc:
        raise LessonError(str(exc)) from None
    clean = sanitize_fragment(clean)
```

并在 `LessonOutput(...)` 返回时加入 `figures=figures`。

`src/testbridge/studio/prompts.py`：`LESSON_SYSTEM` 增补：

```python
    "7. 每课 1–2 张图；纯概念课至少 1 张。图上不用直接写 svg/img，而是在正文放空挂载点"
    '<div data-tb-figure="FIG-1"></div>，并在 figures 数组中给出规格。\n'
    "   每张图必须有 caption（图注）与 alt（说明图表达的关系），中文≤200 字；"
    "图形 kind 只能是 flow / timeline / block / compare，仅使用本课概念。\n"
    "   正文只允许 figure / figcaption 标签，禁止 svg / img / script / style。\n"
```

原第 7 条“只输出一个 JSON 对象”顺延为第 8 条，输出格式改为：

```python
    '{"manifest": {"title", "minutes", "objectives"}, "html": "...", '
    '"exercises": [...], "resources": [...], "figures": [...]}'
```

`src/testbridge/studio/version.py`：

```python
PROMPT_VERSION = "studio/4"
```

`web/studio.py` `generate_lesson` 写步骤时记录图数：

```python
        store.set_step(
            draft_id, "lessons", lesson_id=lesson_id,
            extra={
                "prompt_version": PROMPT_VERSION,
                "written_at": datetime.now(timezone.utc).isoformat(),
                "figure_count": len(output.figures),
            },
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_studio_lessons.py tests/test_studio_prompts.py tests/test_studio_version.py tests/test_studio_web.py -v`
Expected: PASS（`test_studio_web` 中 `studio/3` 断言改为 `studio/4`；旧课程 `studio/3` 存档不变）

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/studio/lessons.py src/testbridge/studio/prompts.py \
  src/testbridge/studio/version.py web/studio.py tests/test_studio_lessons.py \
  tests/test_studio_prompts.py tests/test_studio_version.py tests/test_studio_web.py
git commit -m "feat: embed lesson figures and require them in prompts"
```

---

### Task 3: 质量检查（缺图 warning / 未解析挂载点 error）

**Files:**
- Create: `src/testbridge/quality/figures.py`
- Modify: `src/testbridge/quality/evaluate.py`
- Test: `tests/test_quality_figures.py` (create)

**Interfaces:**
- Consumes: `ContentPack`、`pack_dir/draft.json`（可选）。
- Produces:
  - `figures.evaluate_figures(pack, prompt_versions: dict[str, str]) -> FigureResult`
  - 错误码 `quality.figure_mount_unresolved`；警告码 `quality.lesson_no_figure`。
  - `evaluate_pack` 自动读取 `draft.json` 的 `steps.lessons[*].prompt_version`。

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_quality_figures.py
import json
from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.quality.evaluate import evaluate_pack
from testbridge.quality.figures import evaluate_figures

FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "minimal-pack"


def copy_pack(tmp_path: Path, body: str | None = None) -> Path:
    import shutil

    root = tmp_path / "pack"
    shutil.copytree(FIXTURE, root)
    if body is not None:
        lesson = root / "modules" / "M01" / "lessons" / "L-ONE.html"
        text = lesson.read_text(encoding="utf-8")
        head, _, _ = text.partition("<article")
        lesson.write_text(head + body, encoding="utf-8")
    return root


def write_draft(root: Path, version: str) -> None:
    (root / "draft.json").write_text(json.dumps({
        "steps": {"lessons": {"L-ONE": {"prompt_version": version}}},
    }), encoding="utf-8")


def test_unresolved_mount_is_an_error(tmp_path: Path) -> None:
    root = copy_pack(
        tmp_path,
        '<article class="tb-lesson"><div data-tb-figure="FIG-1"></div></article>',
    )
    result = evaluate_figures(load_pack(root), {})
    assert any(
        issue.code == "quality.figure_mount_unresolved" for issue in result.errors
    )


def test_new_prompt_without_figure_warns(tmp_path: Path) -> None:
    root = copy_pack(
        tmp_path, '<article class="tb-lesson"><p>正文</p></article>'
    )
    result = evaluate_figures(load_pack(root), {"L-ONE": "studio/4"})
    assert any(issue.code == "quality.lesson_no_figure" for issue in result.warnings)


def test_old_prompt_version_is_skipped(tmp_path: Path) -> None:
    root = copy_pack(
        tmp_path, '<article class="tb-lesson"><p>正文</p></article>'
    )
    result = evaluate_figures(load_pack(root), {"L-ONE": "studio/3"})
    assert not any(issue.code == "quality.lesson_no_figure" for issue in result.warnings)


def test_figure_present_is_clean(tmp_path: Path) -> None:
    root = copy_pack(
        tmp_path,
        '<article class="tb-lesson"><figure class="tb-figure">'
        "<svg></svg><figcaption>x</figcaption></figure></article>",
    )
    result = evaluate_figures(load_pack(root), {"L-ONE": "studio/4"})
    assert result.errors == []
    assert result.warnings == []


def test_evaluate_pack_reads_prompt_versions_from_draft_json(tmp_path: Path) -> None:
    root = copy_pack(tmp_path)
    write_draft(root, "studio/4")

    report = evaluate_pack(root)

    assert any(issue.code == "quality.lesson_no_figure" for issue in report.warnings)


def test_published_pack_has_no_figure_warnings(tmp_path: Path) -> None:
    root = copy_pack(tmp_path)

    report = evaluate_pack(root)

    assert not any(issue.code == "quality.lesson_no_figure" for issue in report.warnings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_quality_figures.py -v`
Expected: FAIL — 模块不存在；`evaluate_pack` 未合并图示检查。

- [ ] **Step 3: Write minimal implementation**

`src/testbridge/quality/figures.py`：

```python
"""Figure coverage and unresolved-mount checks."""

from __future__ import annotations

from dataclasses import dataclass, field

from testbridge.content.repository import ContentPack
from testbridge.quality.report import QualityIssue

MOUNT_MARKER = "data-tb-figure"
FIGURE_MARKER = "<figure"
MIN_FIGURE_VERSION = 4


@dataclass
class FigureResult:
    errors: list[QualityIssue] = field(default_factory=list)
    warnings: list[QualityIssue] = field(default_factory=list)


def _version_number(version: str) -> int:
    prefix, _, suffix = version.partition("/")
    if prefix != "studio":
        return 0
    try:
        return int(suffix)
    except ValueError:
        return 0


def evaluate_figures(
    pack: ContentPack, prompt_versions: dict[str, str]
) -> FigureResult:
    result = FigureResult()
    for lesson in pack.lessons_in_order():
        lesson_id = lesson.manifest.id
        body = lesson.body_html
        if MOUNT_MARKER in body:
            result.errors.append(QualityIssue(
                code="quality.figure_mount_unresolved",
                message=f"{lesson_id} 仍有未解析的图形挂载点",
                severity="error",
                lesson_id=lesson_id,
            ))
            continue
        version = prompt_versions.get(lesson_id, "")
        if _version_number(version) < MIN_FIGURE_VERSION:
            continue
        if FIGURE_MARKER not in body:
            result.warnings.append(QualityIssue(
                code="quality.lesson_no_figure",
                message=f"{lesson_id} 没有图示",
                severity="warning",
                lesson_id=lesson_id,
            ))
    return result
```

`src/testbridge/quality/evaluate.py`：读取 draft 元数据并合并：

```python
import json
from testbridge.quality.figures import evaluate_figures


def _prompt_versions(pack_dir: Path) -> dict[str, str]:
    path = pack_dir / "draft.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    steps = data.get("steps") if isinstance(data, dict) else None
    lessons = (steps or {}).get("lessons") if isinstance(steps, dict) else None
    if not isinstance(lessons, dict):
        return {}
    versions: dict[str, str] = {}
    for lesson_id, entry in lessons.items():
        if isinstance(entry, dict) and entry.get("prompt_version"):
            versions[str(lesson_id)] = str(entry["prompt_version"])
    return versions
```

在 `evaluate_pack` 中：

```python
    figures = evaluate_figures(pack, _prompt_versions(pack_dir))
    return build_report(
        structural.metrics + provenance.metrics,
        structural.errors + provenance.errors + figures.errors,
        structural.warnings + provenance.warnings + figures.warnings,
        ...
    )
```

Note: `build_report` sorts errors/warnings by `_issue_key`, which handles `lesson_id`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_quality_figures.py tests/test_quality_rules.py tests/test_studio_quality.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/quality/figures.py src/testbridge/quality/evaluate.py \
  tests/test_quality_figures.py
git commit -m "feat: check lesson figure coverage"
```

---

### Task 4: 文档与全量验收

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/OPTIMIZATION.md`
- Modify: `docs/superpowers/specs/2026-10-26-o2-lesson-figures-design.md`
- Modify: `README.md`（若已有 Studio 写课说明，补一句图由本地渲染、无外部请求）

- [ ] **Step 1: Update the spec status**

```markdown
- 状态：Implemented，2026-10-27
```

- [ ] **Step 2: Update ROADMAP/OPTIMIZATION**

在 ROADMAP 优化清单表中把 O2 标记为「已完成」，并新增：

```markdown
## O2 课程图文并茂（已完成，2026-10-27）

- 写课输出 `figures` 规格：flow / timeline / block / compare；服务端确定性渲染内联 SVG。
- 每课 1–2 张图；`caption` / `alt` 必填；正文禁止直接 `<svg>` 或外部 `<img>`。
- 挂载点缺失/重复/多余、规格非法 → `LessonError`，沿用一次重试。
- 净化器白名单增加 `title` / `desc` / `role` / aria 属性 / `font-weight` / `fill-opacity`；
  仍禁止 `style`、`script`、事件属性与外部 URL。
- 质量：`quality.lesson_no_figure` 仅对 `studio/4` 草稿 warning；
  `quality.figure_mount_unresolved` 为硬错误；分数基线不变。
- prompt 版本 `studio/4`；旧草稿保持旧版本，不自动迁移。
- `tb build` 产物内联 SVG，离线可用，无外部请求。

**未自动化：** 2×2 草稿的真实模型生成验收（需配置模型服务）留待你在真实环境跑一次。
```

并把验证命令与真实输出贴入（`pytest`、两个包 `validate`、`quality`）。

- [ ] **Step 3: Run the full verification**

```bash
.venv/Scripts/python -m pytest -q
PYTHONPATH=src .venv/Scripts/python -m testbridge.cli validate content-packs/ros2-qos
PYTHONPATH=src .venv/Scripts/python -m testbridge.cli validate content-packs/sample-sensors
PYTHONPATH=src .venv/Scripts/python -m testbridge.cli quality content-packs/sample-sensors
PYTHONPATH=src .venv/Scripts/python -m testbridge.cli quality content-packs/robot-quality-system
```

Expected: pytest 全绿（3 deselected）；两包 0/0；quality 100/100。

- [ ] **Step 4: Commit**

```bash
git add docs/ROADMAP.md docs/OPTIMIZATION.md README.md \
  docs/superpowers/specs/2026-10-26-o2-lesson-figures-design.md
git commit -m "docs: record O2 completion"
```

---

## Self-Review

**Spec coverage:**

| Spec 章节 | 任务 |
|---|---|
| §3 图形规格与字段限制 | Task 1 |
| §4.1 挂载规则 / 禁止直接 SVG/外链图 | Task 1、2 |
| §4.2 解析、渲染、嵌入、二次净化 | Task 1、2 |
| §5 提示词与 `studio/4` | Task 2 |
| §6 质量 warning / 硬错误 | Task 3 |
| §7 样式与构建 | 已有 O5 `.tb-figure` 样式；Task 4 验收 |
| §8 测试矩阵 | 各任务 + Task 4 回归 |

**已知取舍：**

- 渲染器只做四类图的简单布局；复杂拓扑仍会显得刻板（spec 已接受）。
- 每课图数上限未硬校验（spec 只要求提示模型 1–2 张），避免额外误伤旧输出。
- 质量指标不含图示分数，仅 warning + 硬错误，保证已发布包基线不变。
- 正文如已含合法内联 `<figure>`（旧内容），不报错；只有未解析挂载点才硬错误。
