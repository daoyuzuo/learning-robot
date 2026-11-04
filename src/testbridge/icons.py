"""Lucide icon path data used by TestBridge, vendored for offline use.

Source: https://github.com/lucide-icons/lucide (ISC license; the subset derived
from Feather is MIT). Only the path/circle/rect/polyline geometry is kept; the
shared presentation attributes live in the ``icon()`` macro so every icon
inherits stroke width and colour from CSS (``currentColor``), which is what
makes the sprite work in both light and dark mode.

Do not edit the path data by hand: it is copied verbatim from the upstream SVG
files so the artwork stays pixel-identical to Lucide. See
``web/static/LICENSES.md`` for the full license text.
"""

from __future__ import annotations

# name -> tuple of SVG child elements (paths/circles/rects/polylines)
# fmt: off
ICONS: dict[str, tuple[str, ...]] = {
    "house": (
        '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/>',
        '<path d="M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    ),
    "calendar-days": (
        '<path d="M8 2v3"/>',
        '<path d="M16 2v3"/>',
        '<rect x="3" y="3" width="18" height="18" rx="2"/>',
        '<path d="M3 9h18"/>',
        '<path d="M8 13h.01"/>',
        '<path d="M12 13h.01"/>',
        '<path d="M16 13h.01"/>',
        '<path d="M8 17h.01"/>',
        '<path d="M12 17h.01"/>',
        '<path d="M16 17h.01"/>',
    ),
    "network": (
        '<rect x="16" y="16" width="6" height="6" rx="1"/>',
        '<rect x="2" y="16" width="6" height="6" rx="1"/>',
        '<rect x="9" y="2" width="6" height="6" rx="1"/>',
        '<path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/>',
        '<path d="M12 12V8"/>',
    ),
    "refresh-cw": (
        '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>',
        '<path d="M21 3v5h-5"/>',
        '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>',
        '<path d="M8 16H3v5"/>',
    ),
    "trending-up": (
        '<path d="M16 7h6v6"/>',
        '<path d="m22 7-8.5 8.5-5-5L2 17"/>',
    ),
    "mic": (
        '<path d="M12 19v3"/>',
        '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>',
        '<rect x="9" y="2" width="6" height="13" rx="3"/>',
    ),
    "target": (
        '<circle cx="12" cy="12" r="10"/>',
        '<circle cx="12" cy="12" r="6"/>',
        '<circle cx="12" cy="12" r="2"/>',
    ),
    "briefcase": (
        '<path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
        '<rect width="20" height="14" x="2" y="6" rx="2"/>',
    ),
    "play": (
        '<path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"/>',
    ),
    "chevron-left": ('<path d="m15 18-6-6 6-6"/>',),
    "chevron-right": ('<path d="m9 18 6-6-6-6"/>',),
    "chevron-down": ('<path d="m6 9 6 6 6-6"/>',),
    "check": ('<path d="M20 6 9 17l-5-5"/>',),
    "circle-check": (
        '<circle cx="12" cy="12" r="10"/>',
        '<path d="m16 9-5.5 5.5L8 12"/>',
    ),
    "circle-x": (
        '<circle cx="12" cy="12" r="10"/>',
        '<path d="m15 9-6 6"/>',
        '<path d="m9 9 6 6"/>',
    ),
    "x": (
        '<path d="M18 6 6 18"/>',
        '<path d="m6 6 12 12"/>',
    ),
    "triangle-alert": (
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>',
        '<path d="M12 9v4"/>',
        '<path d="M12 17h.01"/>',
    ),
    "info": (
        '<circle cx="12" cy="12" r="10"/>',
        '<path d="M12 16v-4"/>',
        '<path d="M12 8h.01"/>',
    ),
    "clock": (
        '<circle cx="12" cy="12" r="10"/>',
        '<path d="M12 6v6l4 2"/>',
    ),
    "book-open": (
        '<path d="M12 5v16"/>',
        '<path d="M20.001 19A2 2 0 0022 17V5a2 2 0 00-1.999-2L16 3.002A5 5 0 0012 5a5 5 0 00-4-2H4a2 2 0 00-2 2v12a2 2 0 001.999 2H8a5 5 0 014 2 5 5 0 014-2z"/>',
    ),
    "lightbulb": (
        '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/>',
        '<path d="M9 18h6"/>',
        '<path d="M10 22h4"/>',
    ),
    "send": (
        '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/>',
        '<path d="m21.854 2.147-10.94 10.939"/>',
    ),
    "external-link": (
        '<path d="M15 3h6v6"/>',
        '<path d="M10 14 21 3"/>',
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    ),
    "inbox": (
        '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/>',
        '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    ),
    "file-text": (
        '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/>',
        '<path d="M14 2v5a1 1 0 0 0 1 1h5"/>',
        '<path d="M10 9H8"/>',
        '<path d="M16 13H8"/>',
        '<path d="M16 17H8"/>',
    ),
    "graduation-cap": (
        '<path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/>',
        '<path d="M22 10v6"/>',
        '<path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>',
    ),
    "sparkles": (
        '<path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z"/>',
        '<path d="M20 2v4"/>',
        '<path d="M22 4h-4"/>',
        '<circle cx="4" cy="20" r="2"/>',
    ),
    "arrow-right": (
        '<path d="M5 12h14"/>',
        '<path d="m12 5 7 7-7 7"/>',
    ),
}
# fmt: on


def icon_markup(name: str, size: int = 16, cls: str = "") -> str:
    """Return a standalone inline ``<svg>`` for ``name``.

    Unknown names fall back to no markup at all so a typo degrades to plain
    text instead of blanking a page.
    """
    parts = ICONS.get(name)
    if parts is None:
        return ""
    classes = f"tb-icon {cls}".strip()
    return (
        f'<svg class="{classes}" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="1.75" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" focusable="false">'
        + "".join(parts)
        + "</svg>"
    )