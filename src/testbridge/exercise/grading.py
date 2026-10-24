"""Deterministic grading for P1 exercise types."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from testbridge.contract.models import Exercise, ShortAnswer

Outcome = Literal["correct", "incorrect", "partial", "submitted"]
PUNCTUATION_RE = re.compile(r"[\s,，。.!！?？;；:：、\"'“”‘’()（）\[\]【】]+")


@dataclass(frozen=True)
class GradeResult:
    outcome: Outcome
    correct: bool | None
    score: float | None
    max_score: float | None
    feedback: str
    details: dict[str, Any] = field(default_factory=dict)


def normalize(text: str) -> str:
    return PUNCTUATION_RE.sub("", str(text)).lower()


def grade(exercise: Exercise, response: Any) -> GradeResult:
    if exercise.type == "single_choice":
        selected = response if isinstance(response, str) else None
        ok = selected == exercise.answer
        return GradeResult(
            "correct" if ok else "incorrect", ok, 1.0 if ok else 0.0, 1.0,
            "回答正确。" if ok else "再想想。", {"selected": selected},
        )

    if exercise.type == "multi_choice":
        expected = set(exercise.answer or [])
        selected = set(response or []) if isinstance(response, list) else set()
        hits = len(expected & selected)
        union = expected | selected
        score = hits / len(union) if union else 0.0
        ok = selected == expected
        outcome: Outcome = "correct" if ok else ("partial" if hits else "incorrect")
        return GradeResult(
            outcome, ok, score, 1.0,
            "全对。" if ok else f"命中了 {hits}/{len(expected)} 个正确项。",
            {
                "selected": sorted(selected),
                "expected": sorted(expected),
                "missing": sorted(expected - selected),
                "false_positives": sorted(selected - expected),
            },
        )

    if exercise.type == "short_answer":
        answer = exercise.answer
        if not isinstance(answer, ShortAnswer):
            raise ValueError("short_answer is missing accepted keywords")
        text = normalize(response)
        matched = [item for item in answer.accepted if normalize(item) in text]
        ok = len(matched) >= answer.min_hits
        score = len(matched) / len(answer.accepted)
        return GradeResult(
            "correct" if ok else "incorrect", ok, score, 1.0,
            "命中关键点。" if ok else "关键点不足，再看一遍材料。",
            {"matched": matched, "missing": [item for item in answer.accepted if item not in matched]},
        )

    if exercise.type == "self_assess":
        checked = set(response.get("checked", [])) if isinstance(response, dict) else set()
        score = sum(item.weight for item in exercise.rubric if item.dimension in checked)
        return GradeResult(
            "submitted", None, score, 1.0, "已记录自评。", {"checked": sorted(checked)},
        )

    if exercise.type == "artifact":
        payload = response if isinstance(response, dict) else {}
        raw_path = payload.get("path")
        path = raw_path.strip() if isinstance(raw_path, str) else ""
        if not path:
            return GradeResult("incorrect", False, 0.0, 1.0, "请填写附件路径。", dict(payload))
        checked = set(payload.get("checked", []))
        score = sum(item.weight for item in exercise.rubric if item.dimension in checked)
        return GradeResult("submitted", None, score, 1.0, "已记录产出物。", payload)

    raise ValueError(f"unsupported exercise type: {exercise.type}")


def get_hint(exercise: Exercise, level: int) -> str | None:
    for hint in exercise.hints:
        if hint.level == level:
            return hint.text
    return None
