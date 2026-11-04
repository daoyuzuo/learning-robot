"""Structural checks on the single shared stylesheet.

These do not try to parse CSS. They pin the handful of invariants the
redesign depends on: every token a template references exists, dark mode
overrides every surface token, the table fix that stopped headers from
wrapping is present, and nothing reaches out to a network resource.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).parents[1] / "web" / "static" / "tb.css").read_text(
    encoding="utf-8"
)


def test_dark_mode_overrides_every_surface_token() -> None:
    dark = CSS.split("@media (prefers-color-scheme: dark)", 1)[1]
    block = dark.split("}", 1)[0]
    for token in (
        "--tb-bg",
        "--tb-bg-elevated",
        "--tb-bg-sunken",
        "--tb-ink",
        "--tb-line",
    ):
        assert f"{token}:" in block


def test_every_var_reference_is_defined() -> None:
    defined = set(re.findall(r"(--tb-[\w-]+)\s*:", CSS))
    used = set(re.findall(r"var\((--tb-[\w-]+)", CSS))
    missing = {name for name in used if name not in defined}
    assert not missing, f"undefined custom properties: {sorted(missing)}"


def test_table_headers_never_wrap() -> None:
    assert re.search(r"th,\s*td[^{]*\{[^}]*white-space:\s*nowrap", CSS)
    assert re.search(r"\.tb-table-wrap table\s*\{[^}]*min-width:\s*\d+px", CSS)


def test_no_external_resource_reference() -> None:
    assert "http://" not in CSS
    assert "https://" not in CSS
    assert "@import" not in CSS


def test_braces_are_balanced() -> None:
    assert CSS.count("{") == CSS.count("}")


def test_reading_measure_and_legacy_class_hooks_survive() -> None:
    # The lesson page is now two panes; the *reading column* keeps the
    # comfortable measure while the shell widens to fit the tutor rail.
    assert re.search(r"\.tb-lesson-column\s*\{[^}]*max-width:\s*46rem", CSS)

    # The shell must be wide enough for the full reading measure (46rem), the
    # rail, the gutter, *and* the page's own horizontal padding. Miss any of
    # those and the column silently shrinks below 46rem while every other
    # assertion still passes.
    spacing = {name: int(value) for name, value in re.findall(
        r"(--tb-space-\d+):\s*(\d+)px", CSS
    )}

    shell = re.search(
        r"\.tb-main\.tb-lesson-main\s*\{[^}]*max-width:\s*(\d+)px", CSS
    )
    assert shell, "lesson shell has no explicit max-width"

    rail = re.search(r"grid-template-columns:\s*minmax\(0,\s*1fr\)\s*(\d+)px", CSS)
    assert rail, "lesson shell has no tutor rail column"

    gap = re.search(r"\.tb-lesson-shell\s*\{[^}]*gap:\s*var\(--tb-space-(\d+)\)", CSS)
    assert gap, "lesson shell loses its gutter"
    gutter = spacing[f"--tb-space-{gap.group(1)}"]

    main_rule = re.search(r"^\.tb-main \{[^}]*\}", CSS, re.MULTILINE)
    assert main_rule, "no base .tb-main rule"
    padding = re.search(
        r"padding:\s*var\(--tb-space-\d+\)\s*var\(--tb-space-(\d+)\)", main_rule.group(0)
    )
    assert padding, "base .tb-main loses its horizontal padding"
    side_padding = spacing[f"--tb-space-{padding.group(1)}"]

    needed = 46 * 16 + int(rail.group(1)) + gutter + side_padding * 2
    assert int(shell.group(1)) >= needed, (
        f"shell max-width {shell.group(1)}px cannot fit a 46rem column plus a "
        f"{rail.group(1)}px rail, {gutter}px gutter and {side_padding * 2}px padding "
        f"(needs {needed}px)"
    )
    # Existing templates and tests reference these class names.
    for hook in (
        ".tb-card",
        ".tb-badge",
        ".tb-callout",
        ".tb-table-wrap",
        ".tb-plan",
        ".tb-skip-link",
        ".tb-nav",
        ".tb-tutor",
        ".tb-resources",
        ".tb-btn-primary",
    ):
        assert hook in CSS