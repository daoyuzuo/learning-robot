"""Post-submission review: context, prompt, parsing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from testbridge.content.repository import ContentPack
from testbridge.contract.models import ShortAnswer
from testbridge.evidence.store import EvidenceEvent
from testbridge.tutor.context import build_context

MAX_EXPLANATION_CHARS = 4000
MAX_LIST_ITEMS = 3
VERDICTS = ("correct", "partial", "incorrect")

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


@dataclass(frozen=True)
class ReviewContext:
    lesson_id: str
    exercise_id: str
    exercise_type: str
    text: str
    dimensions: list[str]


@dataclass(frozen=True)
class RubricVerdict:
    dimension: str
    met: bool
    comment: str


@dataclass(frozen=True)
class TutorReview:
    verdict: str
    explanation: str
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    rubric: list[RubricVerdict] = field(default_factory=list)
    suggested_score: float | None = None


REVIEW_SYSTEM_PROMPT = (
    "你是 TestBridge 的讲评助手。学习者刚提交了一道练习，请针对这次作答讲评。\n"
    "规则：\n"
    "1. 用中文，先给结论，再给理由，300 字以内。\n"
    "2. 指出具体错在哪一步、或哪里写得好；不要泛泛而谈。\n"
    "3. 只使用 <lesson> 与 <submission> 里的信息；不要臆造 rubric 之外的维度。\n"
    "4. 只输出一个 JSON 对象，不要代码块、不要额外文字。格式：\n"
    '{"verdict": "correct|partial|incorrect", "explanation": "...", '
    '"strengths": ["..."], "gaps": ["..."], '
    '"rubric": [{"dimension": "...", "met": true, "comment": "..."}], '
    '"suggested_score": 0.0}'
)


def _answer_text(exercise) -> str:
    answer = exercise.answer
    if answer is None:
        return "（无）"
    if isinstance(answer, ShortAnswer):
        return (
            "接受关键词：" + "、".join(answer.accepted)
            + f"（至少命中 {answer.min_hits} 个）"
        )
    if isinstance(answer, list):
        return "、".join(answer)
    return str(answer)


def build_review_context(pack: ContentPack, event: EvidenceEvent) -> ReviewContext:
    lesson_id = event.lesson_id or ""
    exercise = pack.exercises.get(event.exercise_id or "")
    if exercise is None:
        raise KeyError(f"unknown exercise: {event.exercise_id}")

    base = build_context(pack, lesson_id).text
    options = " ".join(f"{option.id}. {option.text}" for option in exercise.options)
    rubric_lines = [
        f"- {item.dimension}（权重 {item.weight}）：{item.criteria}"
        for item in exercise.rubric
    ]
    response = event.payload.get("response")
    lines = [
        "<submission>",
        f"题目：{exercise.prompt}",
        f"选项：{options or '（无）'}",
        "学习者答案：" + json.dumps(response, ensure_ascii=False),
        f"系统判定：{event.outcome}（{event.score}/{event.max_score}）",
        f"正确答案：{_answer_text(exercise)}",
        f"既有解析：{exercise.explanation or '（无）'}",
        "rubric：\n" + ("\n".join(rubric_lines) if rubric_lines else "（无）"),
        "</submission>",
    ]
    return ReviewContext(
        lesson_id=lesson_id,
        exercise_id=exercise.id,
        exercise_type=exercise.type,
        text=base + "\n\n" + "\n".join(lines),
        dimensions=[item.dimension for item in exercise.rubric],
    )


def render_review_prompt(context: ReviewContext) -> str:
    return "\n".join([
        f'<lesson id="{context.lesson_id}">',
        context.text,
        "</lesson>",
    ])


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item][:MAX_LIST_ITEMS]


def parse_review(raw: str, dimensions: list[str]) -> TutorReview:
    text = _FENCE_RE.sub("", raw.strip()).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    if not isinstance(data, dict):
        return TutorReview(
            verdict="partial", explanation=text[:MAX_EXPLANATION_CHARS]
        )

    verdict = data.get("verdict")
    if verdict not in VERDICTS:
        verdict = "partial"

    explanation = data.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        explanation = text
    explanation = explanation.strip()[:MAX_EXPLANATION_CHARS]

    by_dimension = {}
    raw_rubric = data.get("rubric")
    if isinstance(raw_rubric, list):
        for item in raw_rubric:
            if not isinstance(item, dict):
                continue
            dimension = item.get("dimension")
            if dimension in dimensions and dimension not in by_dimension:
                by_dimension[dimension] = RubricVerdict(
                    dimension=dimension,
                    met=bool(item.get("met")),
                    comment=str(item.get("comment") or ""),
                )
    rubric = [by_dimension[item] for item in dimensions if item in by_dimension]

    score = data.get("suggested_score")
    suggested: float | None = None
    if dimensions and isinstance(score, (int, float)) and not isinstance(score, bool):
        suggested = max(0.0, min(1.0, float(score)))

    return TutorReview(
        verdict=verdict,
        explanation=explanation,
        strengths=_strings(data.get("strengths")),
        gaps=_strings(data.get("gaps")),
        rubric=rubric,
        suggested_score=suggested,
    )
