"""Deterministic course plan suggestion and validation.

Pure functions: no LLM, no stores, no learning imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field

UTILIZATION = 0.65
PURPOSES = ("interview", "project", "systematic")
LESSON_MINUTES = {"L2": 30, "L3": 35, "L4": 40}
PROJECT_BONUS = 5
MAX_TOTAL_LESSONS = 15
MAX_MODULES = 3
MAX_LESSONS_PER_MODULE = 5
MIN_LESSON_MINUTES = 20
MAX_LESSON_MINUTES = 60
MAX_MUST_COVER = 10
MUST_COVER_LIMIT = 40
MAX_GUIDANCE = 5
MAX_GUIDANCE_CHARS = 80
MAX_RATIONALE = 500
MAX_CHANGES = 10
MAX_CHANGE_CHARS = 200


class PlanError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class PlanInput:
    weekly_hours: float
    horizon_weeks: int
    purpose: str
    must_cover: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlanSuggestion:
    module_count: int
    lessons_per_module: int
    lesson_minutes: int
    total_lessons: int
    total_minutes: int
    rationale: str


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanError("plan_invalid", "数字字段必须是数值")
    return float(value)


def parse_plan_input(data: dict) -> PlanInput:
    if not isinstance(data, dict):
        raise PlanError("plan_invalid", "计划输入必须是对象")
    weekly_hours = _number(data.get("weekly_hours"))
    horizon_weeks = _number(data.get("horizon_weeks"))
    if not 0 < weekly_hours <= 80:
        raise PlanError("plan_invalid", "每周小时必须在 0–80 之间")
    if not 1 <= horizon_weeks <= 52 or horizon_weeks != int(horizon_weeks):
        raise PlanError("plan_invalid", "周期必须是 1–52 的整数")
    purpose = str(data.get("purpose") or "systematic").strip()
    if purpose not in PURPOSES:
        raise PlanError("plan_invalid", "目的必须是 interview / project / systematic")
    must_cover = data.get("must_cover") or []
    if not isinstance(must_cover, list) or len(must_cover) > MAX_MUST_COVER:
        raise PlanError("plan_invalid", f"必须覆盖最多 {MAX_MUST_COVER} 项")
    topics = []
    for item in must_cover:
        if not isinstance(item, str) or len(item.strip()) > MUST_COVER_LIMIT:
            raise PlanError("plan_invalid", f"必须覆盖每项不超过 {MUST_COVER_LIMIT} 字")
        if item.strip():
            topics.append(item.strip())
    return PlanInput(weekly_hours, int(horizon_weeks), purpose, topics)


def _lesson_minutes(level: str, purpose: str) -> int:
    base = LESSON_MINUTES.get(level, 30)
    minutes = base + (PROJECT_BONUS if purpose == "project" else 0)
    return max(MIN_LESSON_MINUTES, min(MAX_LESSON_MINUTES, minutes))


def suggest_plan(plan_input: PlanInput, level: str) -> PlanSuggestion:
    minutes = _lesson_minutes(level, plan_input.purpose)
    budget = plan_input.weekly_hours * 60 * plan_input.horizon_weeks * UTILIZATION
    raw_lessons = int(budget / minutes + 0.5)
    capped = raw_lessons > MAX_TOTAL_LESSONS
    total = max(3, min(MAX_TOTAL_LESSONS, raw_lessons))
    modules = max(1, min(MAX_MODULES, -(-total // MAX_LESSONS_PER_MODULE)))
    per_module = -(-total // modules)
    total = modules * per_module
    rationale = (
        f"按每周 {plan_input.weekly_hours:g} 小时 × {plan_input.horizon_weeks} 周、"
        f"利用率 {UTILIZATION:g} 估算，单课 {minutes} 分钟，"
        f"安排 {modules} 个模块、每模块 {per_module} 课，共 {total} 课。"
    )
    if capped:
        rationale += (
            f"当前上限 {MAX_TOTAL_LESSONS} 课，建议拆成两个包分别学习。"
        )
    return PlanSuggestion(
        module_count=modules,
        lessons_per_module=per_module,
        lesson_minutes=minutes,
        total_lessons=total,
        total_minutes=total * minutes,
        rationale=rationale,
    )


def _int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PlanError("plan_invalid", f"{field_name} 必须是整数")
    return value


def validate_plan(plan: dict) -> None:
    if not isinstance(plan, dict):
        raise PlanError("plan_invalid", "计划必须是对象")
    computed = plan.get("computed")
    if not isinstance(computed, dict):
        raise PlanError("plan_invalid", "计划缺少 computed")
    modules = _int(computed.get("module_count"), "module_count")
    per_module = _int(computed.get("lessons_per_module"), "lessons_per_module")
    minutes = _int(computed.get("lesson_minutes"), "lesson_minutes")
    total = _int(computed.get("total_lessons"), "total_lessons")
    if not 1 <= modules <= MAX_MODULES:
        raise PlanError("plan_invalid", "模块数必须在 1–3 之间")
    if not 1 <= per_module <= MAX_LESSONS_PER_MODULE:
        raise PlanError("plan_invalid", "每模块课数必须在 1–5 之间")
    if modules * per_module > MAX_TOTAL_LESSONS:
        raise PlanError("plan_invalid", "总课数不能超过 15")
    if total != modules * per_module:
        raise PlanError("plan_invalid", "总课数与模块数不匹配")
    if not MIN_LESSON_MINUTES <= minutes <= MAX_LESSON_MINUTES:
        raise PlanError("plan_invalid", "单课分钟必须在 20–60 之间")
    guidance = plan.get("guidance") or []
    if not isinstance(guidance, list) or len(guidance) > MAX_GUIDANCE:
        raise PlanError("plan_invalid", f"写作方向最多 {MAX_GUIDANCE} 条")
    for item in guidance:
        if not isinstance(item, str) or not item.strip() or len(item) > MAX_GUIDANCE_CHARS:
            raise PlanError("plan_invalid", f"写作方向每条不超过 {MAX_GUIDANCE_CHARS} 字")
