"""Server-rendered prerequisite graph as inline SVG."""

from __future__ import annotations

import html
from typing import Any

NODE_WIDTH = 140
NODE_HEIGHT = 44
GAP_X = 20
GAP_Y = 46
MARGIN = 12
TITLE_LIMIT = 10

LEVEL_FILL = {
    "L0": "#f3f4f6",
    "L1": "#dbeafe",
    "L2": "#bfdbfe",
    "L3": "#93c5fd",
    "L4": "#60a5fa",
}


def _concepts(pack: Any) -> dict[str, Any]:
    return getattr(pack, "concepts", {}) or {}


def graph_levels(pack: Any) -> dict[str, int]:
    """Longest prerequisite path from a root; roots are level 0."""
    concepts = _concepts(pack)
    memo: dict[str, int] = {}

    def level(concept_id: str, stack: frozenset[str]) -> int:
        if concept_id in memo:
            return memo[concept_id]
        if concept_id in stack:
            return 0
        parents = [
            item
            for item in concepts[concept_id].prerequisites
            if item in concepts and item != concept_id
        ]
        value = 0 if not parents else 1 + max(
            level(item, stack | {concept_id}) for item in parents
        )
        memo[concept_id] = value
        return value

    for concept_id in sorted(concepts):
        level(concept_id, frozenset())
    return memo


def _shorten(title: str) -> str:
    return title if len(title) <= TITLE_LIMIT else title[:TITLE_LIMIT] + "…"


def prerequisite_svg(pack: Any, views: dict[str, Any] | None = None) -> str:
    concepts = _concepts(pack)
    if not concepts:
        return ""

    levels = graph_levels(pack)
    layers: dict[int, list[str]] = {}
    for concept_id in sorted(concepts):
        layers.setdefault(levels[concept_id], []).append(concept_id)

    layer_count = max(layers) + 1
    widest = max(len(items) for items in layers.values())
    width = MARGIN * 2 + widest * NODE_WIDTH + (widest - 1) * GAP_X
    height = MARGIN * 2 + layer_count * NODE_HEIGHT + (layer_count - 1) * GAP_Y

    positions: dict[str, tuple[int, int]] = {}
    for level, items in layers.items():
        for index, concept_id in enumerate(items):
            positions[concept_id] = (
                MARGIN + index * (NODE_WIDTH + GAP_X),
                MARGIN + level * (NODE_HEIGHT + GAP_Y),
            )

    edges = []
    for concept_id in sorted(concepts):
        child_x, child_y = positions[concept_id]
        for parent_id in concepts[concept_id].prerequisites:
            if parent_id not in positions:
                continue
            parent_x, parent_y = positions[parent_id]
            edges.append(
                f'<line class="tb-graph-edge" '
                f'x1="{parent_x + NODE_WIDTH // 2}" y1="{parent_y + NODE_HEIGHT}" '
                f'x2="{child_x + NODE_WIDTH // 2}" y2="{child_y}" '
                f'stroke="#9ca3af" stroke-width="1.5"/>'
            )

    nodes = []
    for concept_id in sorted(concepts):
        concept = concepts[concept_id]
        x, y = positions[concept_id]
        view = (views or {}).get(concept_id)
        mastery_level = getattr(view, "level", "L0")
        estimate = getattr(view, "estimate", 0.0)
        fill = LEVEL_FILL.get(mastery_level, LEVEL_FILL["L0"])
        nodes.append(
            f'<g data-concept="{html.escape(concept_id)}">'
            f'<rect x="{x}" y="{y}" width="{NODE_WIDTH}" height="{NODE_HEIGHT}" '
            f'rx="8" fill="{fill}" stroke="#6b7280" stroke-width="1"/>'
            f'<text x="{x + 10}" y="{y + 18}" font-size="12" fill="#111827">'
            f"{html.escape(_shorten(concept.title))}</text>"
            f'<text x="{x + 10}" y="{y + 34}" font-size="11" fill="#4b5563">'
            f"{html.escape(mastery_level)} · {estimate:.2f}</text>"
            f"</g>"
        )

    return (
        f'<svg class="tb-graph" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="概念先修关系图">'
        + "".join(edges)
        + "".join(nodes)
        + "</svg>"
    )
