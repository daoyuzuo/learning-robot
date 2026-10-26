import itertools
import re

import pytest

from testbridge.contract.sanitize import sanitize_fragment
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


@pytest.mark.parametrize("spec", [FLOW, TIMELINE, BLOCK, COMPARE])
def test_render_survives_sanitizer(spec) -> None:
    svg = render_figure(parse_figures([spec], {"c"})[0])
    clean = sanitize_fragment(svg)
    assert clean.count("<tspan") == svg.count("<tspan")
    assert "dy=" in clean
    assert "<polygon" in clean or "<circle" in clean or "<rect" in clean
    assert 'viewbox="0 0' in clean.lower()


def test_render_wide_flow_stays_inside_viewbox() -> None:
    wide = {
        **FLOW,
        "nodes": [{"id": f"n{i}", "label": f"步骤{i}"} for i in range(1, 9)],
        "edges": [{"from": f"n{i}", "to": f"n{i + 1}"} for i in range(1, 8)],
    }
    svg = render_figure(parse_figures([wide], {"c"})[0])
    boxes = [
        (float(x), float(w))
        for x, w in re.findall(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)"', svg)
    ]
    assert len(boxes) == 8
    assert all(x >= 0 for x, _ in boxes)
    assert all(x + w <= 800 for x, w in boxes)
    for (x, w), (next_x, _) in itertools.pairwise(boxes):
        assert x + w <= next_x


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
