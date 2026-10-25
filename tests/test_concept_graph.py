from pathlib import Path
from types import SimpleNamespace

from testbridge.concept_graph import graph_levels, prerequisite_svg
from testbridge.content.repository import load_pack

SAMPLE = Path(__file__).parents[1] / "content-packs" / "ros2-qos"
PACK = load_pack(SAMPLE)


def test_levels_follow_longest_prerequisite_chain() -> None:
    levels = graph_levels(PACK)
    assert levels["ros2-communication-model"] == 0
    assert levels["dds-qos-policies"] == 1
    assert levels["qos-compatibility"] == 2
    assert levels["qos-observability"] == 3
    assert levels["qos-testing"] == 4


def test_svg_contains_every_concept_and_prerequisite_edge() -> None:
    svg = prerequisite_svg(PACK)
    for concept_id in PACK.concepts:
        assert f'data-concept="{concept_id}"' in svg
    expected_edges = sum(
        len(concept.prerequisites) for concept in PACK.concepts.values()
    )
    assert svg.count('class="tb-graph-edge"') == expected_edges


def test_svg_is_well_formed_and_escaped() -> None:
    svg = prerequisite_svg(PACK)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "viewBox=" in svg


def test_empty_pack_returns_empty_string() -> None:
    empty = SimpleNamespace(concepts={})

    assert prerequisite_svg(empty) == ""
    assert graph_levels(empty) == {}
