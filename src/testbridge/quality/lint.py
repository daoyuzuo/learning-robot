"""Deterministic content lint rules inspired by teaching best practices."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from testbridge.content.repository import ContentPack

_PLACEHOLDER_RE = re.compile(
    r"(待填|TODO|example\.com|lorem ipsum)", re.IGNORECASE
)
_ANSWER_LEAK_RE = re.compile(r'"(answer|explanation|accepted|rubric)"\s*:')
_UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*"
    r"(?:ms|s|mm|cm|m/s|m·s|%|°C|kg|Hz|N·m|Nm|N|rad/s|rad|V|A|W)"
    r"(?![A-Za-z])"
)
_REQUIRED_TRUST = {"A", "B"}


@dataclass(frozen=True)
class LintIssue:
    code: str
    message: str
    severity: str = "error"
    lesson_id: str | None = None
    exercise_id: str | None = None

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "lesson_id": self.lesson_id,
            "exercise_id": self.exercise_id,
        }


@dataclass(frozen=True)
class LintReport:
    issues: list[LintIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[LintIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[LintIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }


def _plain_text(body_html: str) -> str:
    return re.sub(r"<[^>]+>", "", body_html)


def _primary_source(pack: ContentPack, lesson):
    for resource_id in lesson.manifest.resources:
        resource = pack.resources.get(resource_id)
        if resource and resource.role == "required" and resource.trust in _REQUIRED_TRUST:
            return resource
    return None


def _check_lesson(pack: ContentPack, lesson) -> list[LintIssue]:
    issues: list[LintIssue] = []
    manifest = lesson.manifest
    level = manifest.target_level
    text = _plain_text(lesson.body_html)

    if _PLACEHOLDER_RE.search(text):
        issues.append(LintIssue(
            "lint.placeholder", "正文包含占位符", "error", manifest.id
        ))
    if _ANSWER_LEAK_RE.search(lesson.body_html):
        issues.append(LintIssue(
            "lint.answer_leak", "正文包含答案/解析字段", "error", manifest.id
        ))

    primary = _primary_source(pack, lesson)
    if primary is None or not primary.why.strip():
        issues.append(LintIssue(
            "lint.primary_source_missing",
            "缺少带 why 的 required A/B 主来源",
            "error",
            manifest.id,
        ))

    if not _UNIT_RE.search(text):
        severity = "error" if level in {"L3", "L4"} else "warning"
        issues.append(LintIssue(
            "lint.no_worked_example",
            "正文没有数字+单位的工程实例",
            severity,
            manifest.id,
        ))

    objectives = [f"O{index + 1}" for index in range(len(manifest.objectives))]
    mapping = manifest.objective_map
    if not mapping:
        severity = "error" if level in {"L3", "L4"} else "warning"
        issues.append(LintIssue(
            "lint.objective_map_missing",
            "缺少 objective_map",
            severity,
            manifest.id,
        ))
    else:
        for objective_id in objectives:
            if not mapping.get(objective_id):
                issues.append(LintIssue(
                    "lint.objective_unmapped",
                    f"{objective_id} 没有映射到练习",
                    "error",
                    manifest.id,
                ))
        for objective_id, exercise_ids in mapping.items():
            if objective_id not in objectives:
                issues.append(LintIssue(
                    "lint.objective_unknown",
                    f"{objective_id} 不在 objectives 范围内",
                    "error",
                    manifest.id,
                ))
            for exercise_id in exercise_ids:
                if exercise_id not in manifest.exercises:
                    issues.append(LintIssue(
                        "lint.objective_exercise_unknown",
                        f"{objective_id} 引用了本课未列出的 {exercise_id}",
                        "error",
                        manifest.id,
                    ))
    return issues


def _check_lesson_order(pack: ContentPack) -> list[LintIssue]:
    """Every prerequisite must be taught no later than the lesson using it.

    A reordered course can look plausible lesson by lesson while a concept is
    explained before its prerequisite ever appears. Lesson position, not file
    numbering, is what the learner experiences, so this compares against the
    order ``lessons_in_order()`` yields.
    """
    lessons = pack.lessons_in_order()
    first_seen: dict[str, int] = {}
    for index, lesson in enumerate(lessons):
        for concept_id in lesson.manifest.concepts:
            first_seen.setdefault(concept_id, index)

    issues: list[LintIssue] = []
    for index, lesson in enumerate(lessons):
        for concept_id in lesson.manifest.concepts:
            concept = pack.concepts.get(concept_id)
            if concept is None:
                continue
            for prerequisite in concept.prerequisites:
                taught_at = first_seen.get(prerequisite)
                if taught_at is None or taught_at <= index:
                    continue
                issues.append(LintIssue(
                    "lint.lesson_order",
                    f"{concept_id} 的先修 {prerequisite} 在第 {taught_at + 1} 课，"
                    f"晚于本课（第 {index + 1} 课）",
                    "error",
                    lesson.manifest.id,
                ))
    return issues


def _check_quiz(pack: ContentPack) -> list[LintIssue]:
    issues: list[LintIssue] = []
    choice = [
        exercise
        for exercise in pack.exercises.values()
        if exercise.type in {"single_choice", "multi_choice"}
    ]
    if not choice:
        return issues

    positions: Counter[str] = Counter()
    longest_correct = 0
    for exercise in choice:
        option_ids = [option.id for option in exercise.options]
        if exercise.type == "single_choice":
            index = option_ids.index(exercise.answer)
        else:
            index = min(option_ids.index(answer) for answer in exercise.answer)
        positions[option_ids[index]] += 1

        lengths = [len(option.text) for option in exercise.options]
        if lengths[index] == max(lengths):
            longest_correct += 1
        ratio = max(lengths) / min(lengths) if min(lengths) else 0
        if ratio > 3.0:
            issues.append(LintIssue(
                "lint.quiz_option_length",
                f"选项长度比 {ratio:.1f} > 3.0",
                "error",
                exercise_id=exercise.id,
            ))
        elif ratio > 2.0:
            issues.append(LintIssue(
                "lint.quiz_option_length",
                f"选项长度比 {ratio:.1f} > 2.0",
                "warning",
                exercise_id=exercise.id,
            ))

    if len(choice) >= 4:
        max_share = max(positions.values()) / len(choice)
        if max_share > 0.7:
            issues.append(LintIssue(
                "lint.quiz_answer_position",
                f"单一正确位置占比 {max_share:.0%} > 70%",
                "error",
            ))

    if longest_correct / len(choice) > 0.6:
        issues.append(LintIssue(
            "lint.quiz_answer_longest",
            f"正确答案为最长选项占比 {longest_correct / len(choice):.0%} > 60%",
            "warning",
        ))
    return issues


def evaluate_lint(pack: ContentPack) -> LintReport:
    issues: list[LintIssue] = []
    for lesson in pack.lessons_in_order():
        issues.extend(_check_lesson(pack, lesson))
    issues.extend(_check_lesson_order(pack))
    issues.extend(_check_quiz(pack))
    return LintReport(issues=issues)
