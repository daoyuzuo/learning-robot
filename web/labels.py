"""Human-readable labels and date filters shared by every template.

The engine speaks in stable identifiers (``review``, ``L0``, ISO timestamps).
Those are the right thing to store and the wrong thing to show. This module is
the single place that turns them into Chinese copy, so a page never has to
print an internal enum value by accident.

Unknown values pass through unchanged: a new engine enum must degrade to
readable-but-unformatted text, never to a blank cell or a raised exception.
"""

from __future__ import annotations

import math
from datetime import datetime

PLAN_TYPES: dict[str, str] = {
    "review": "复习",
    "new": "新学",
    "weak": "补弱",
}

OUTCOMES: dict[str, str] = {
    "correct": "正确",
    "partial": "部分正确",
    "incorrect": "错误",
    "submitted": "已提交",
}

LEVELS: dict[str, str] = {
    "L0": "L0",
    "L1": "L1",
    "L2": "L2",
    "L3": "L3",
    "L4": "L4",
}

TRUSTS: dict[str, str] = {
    "A": "A",
    "B": "B",
    "C": "C",
    "D": "D",
}

KINDS: dict[str, str] = {
    "exercise_attempt": "练习",
    "exercise": "练习",
    "self_assess": "自评",
    "artifact": "产出物",
    "interview": "面试",
}

_TABLES: dict[str, dict[str, str]] = {
    "plan_type": PLAN_TYPES,
    "outcome": OUTCOMES,
    "level": LEVELS,
    "trust": TRUSTS,
    "kind": KINDS,
}


def label(kind: str, value: object) -> str:
    """Map ``value`` through the table named ``kind``; unknown values survive."""
    if value is None:
        return ""
    table = _TABLES.get(kind, {})
    text = str(value)
    return table.get(text, text)


def label_filter(value: object, kind: str) -> str:
    """Jinja filter form: ``{{ item.type | tb_label("plan_type") }}``.

    Jinja passes the piped value as the first argument, so the filter wraps
    ``label(kind, value)`` instead of being the same callable.
    """
    return label(kind, value)


def plan_type_label(value: object) -> str:
    return label("plan_type", value)


def outcome_label(value: object) -> str:
    return label("outcome", value)


def level_label(value: object) -> str:
    return label("level", value)


def trust_label(value: object) -> str:
    return label("trust", value)


def kind_label(value: object) -> str:
    return label("kind", value)


def _local(value: str) -> datetime | None:
    """Parse an ISO string into local time, or None when unparseable."""
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone()


def format_date(value: object) -> str:
    """``2020-01-02T00:00:00+00:00`` -> ``1月2日`` (local time)."""
    if not value:
        return ""
    text = str(value)
    parsed = _local(text)
    if parsed is None:
        return text
    return f"{parsed.month}月{parsed.day}日"


def format_datetime(value: object) -> str:
    """ISO timestamp -> ``1月2日 11:04`` (local time)."""
    if not value:
        return ""
    text = str(value)
    parsed = _local(text)
    if parsed is None:
        return text
    return f"{parsed.month}月{parsed.day}日 {parsed.hour:02d}:{parsed.minute:02d}"


def excerpt(value: object, limit: int = 40) -> str:
    """Collapse whitespace and truncate with an ellipsis."""
    if not value:
        return ""
    normalized = " ".join(str(value).split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "…"


def register(templates) -> None:
    """Install the filters and the ``label`` global on a Jinja environment."""
    env = templates.env
    env.filters["tb_label"] = label_filter
    env.filters["tb_date"] = format_date
    env.filters["tb_datetime"] = format_datetime
    env.filters["tb_excerpt"] = excerpt
    env.globals["label"] = label
    env.globals["trust_label"] = trust_label
    env.globals["kind_label"] = kind_label
    env.globals["outcome_label"] = outcome_label
    # Percent widths are emitted as utility classes because the app's CSP
    # forbids inline style attributes (style-src 'self').
    env.globals["pct_class"] = pct_class


def pct_class(ratio: object) -> str:
    """Bucket a 0..1 ratio into a ``tb-w-<n>`` class (0-100, step 5).

    CSS cannot compute a width from a data attribute, and CSP forbids the
    inline ``style="width: X%"`` that would otherwise be the obvious way to
    drive these bars, so the stylesheet defines the classes in 5% steps.
    """
    try:
        value = float(ratio)
    except (TypeError, ValueError):
        return "tb-w-0"
    if not math.isfinite(value) or value < 0:
        return "tb-w-0"
    bucket = min(100, max(0, round(value * 100 / 5.0) * 5))
    return f"tb-w-{bucket}"