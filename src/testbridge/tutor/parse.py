"""Parse and constrain the model's JSON reply."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

MAX_ANSWER_CHARS = 8000
MAX_FOLLOWUPS = 3
BASES = ("lesson", "resource", "general")

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


@dataclass(frozen=True)
class TutorAnswer:
    answer: str
    basis: str
    citations: list[str] = field(default_factory=list)
    followups: list[str] = field(default_factory=list)


def _truncate(text: str) -> str:
    if len(text) <= MAX_ANSWER_CHARS:
        return text
    return text[:MAX_ANSWER_CHARS] + "…（已截断）"


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def parse_answer(raw: str, *, headings: list[str], resource_ids: list[str]) -> TutorAnswer:
    text = _FENCE_RE.sub("", raw.strip()).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    if not isinstance(data, dict):
        return TutorAnswer(answer=_truncate(text), basis="general")

    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        answer = text

    basis = data.get("basis")
    if basis not in BASES:
        basis = "general"

    allowed = set(headings) | set(resource_ids)
    citations = [item for item in _strings(data.get("citations")) if item in allowed]

    followups = _strings(data.get("followups"))[:MAX_FOLLOWUPS]
    return TutorAnswer(
        answer=_truncate(answer.strip()),
        basis=basis,
        citations=citations,
        followups=followups,
    )
