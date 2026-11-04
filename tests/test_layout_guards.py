"""Layout guards that CSS alone cannot express.

The redesign promises no horizontal scrolling down to 320px. That is a real
browser property, not something a template assertion can prove, so these tests
pin the two mechanisms it depends on: fixed multi-column grids collapsing, and
wide tables scrolling inside their own frame instead of the page.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).parents[1] / "web" / "static" / "tb.css").read_text(
    encoding="utf-8"
)


def _media_block(max_width: int) -> str:
    """Return the body of the first ``@media (max-width: Npx)`` block."""
    pattern = rf"@media \(max-width: {max_width}px\) \{{"
    match = re.search(pattern, CSS)
    assert match, f"missing @media (max-width: {max_width}px)"
    depth = 0
    start = match.end() - 1
    for index in range(start, len(CSS)):
        char = CSS[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return CSS[start:index]
    raise AssertionError("unbalanced media block")


def test_fixed_grids_collapse_on_narrow_screens() -> None:
    narrow = _media_block(720)
    for selector in (".tb-stat-row-hero", ".tb-split", ".tb-modules"):
        assert selector in narrow, f"{selector} never collapses on small screens"
    assert "grid-template-columns: 1fr" in narrow or "minmax(0, 1fr)" in narrow


def test_lesson_tables_scroll_inside_the_body() -> None:
    # A lesson table wider than a phone must not widen the page.
    assert re.search(
        r"\.tb-lesson table \{[^}]*overflow-x:\s*auto", CSS
    )
    assert re.search(r"\.tb-lesson table \{[^}]*max-width:\s*100%", CSS)


def test_table_wrapper_scrolls_and_page_does_not() -> None:
    assert re.search(r"\.tb-table-wrap \{[^}]*overflow-x:\s*auto", CSS)
    # The base sheet must never set a minimum width on the page body.
    assert "body { min-width" not in CSS