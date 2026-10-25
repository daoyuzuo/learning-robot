"""Deterministic quality rules that only need pack content."""

from __future__ import annotations

from dataclasses import dataclass, field

from testbridge.content.repository import ContentPack
from testbridge.quality.report import QualityIssue, QualityMetric, proportional

LEVEL_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}


@dataclass
class StructuralResult:
    metrics: list[QualityMetric] = field(default_factory=list)
    errors: list[QualityIssue] = field(default_factory=list)
    warnings: list[QualityIssue] = field(default_factory=list)


def _error(code: str, message: str, **kwargs) -> QualityIssue:
    return QualityIssue(code=code, message=message, severity="error", **kwargs)


def _warning(code: str, message: str, **kwargs) -> QualityIssue:
    return QualityIssue(code=code, message=message, severity="warning", **kwargs)


def _level(value: str) -> int:
    return LEVEL_ORDER.get(value, 0)


def _module_concept_ids(pack: ContentPack) -> list[str]:
    seen: list[str] = []
    for module in sorted(pack.modules.values(), key=lambda item: (item.order, item.id)):
        for concept_id in module.concepts:
            if concept_id in pack.concepts and concept_id not in seen:
                seen.append(concept_id)
    return seen


def _lesson_exercises(pack: ContentPack, manifest) -> list:
    return [
        pack.exercises[exercise_id]
        for exercise_id in manifest.exercises
        if exercise_id in pack.exercises
    ]


def _max_level(exercises: list) -> int:
    return max((_level(item.level) for item in exercises), default=0)


def evaluate_structural(pack: ContentPack) -> StructuralResult:
    result = StructuralResult()
    lessons = pack.lessons_in_order()
    concept_ids = _module_concept_ids(pack)
    all_exercises = list(pack.exercises.values())

    covered = {concept_id for item in all_exercises for concept_id in item.concepts}
    missing = [concept_id for concept_id in concept_ids if concept_id not in covered]
    for concept_id in missing:
        result.errors.append(_error(
            "quality.concept_without_exercise",
            f"概念 {concept_id} 没有练习覆盖",
            concept_id=concept_id,
        ))

    for lesson in lessons:
        manifest = lesson.manifest
        exercises = _lesson_exercises(pack, manifest)
        if len(exercises) < 2:
            result.errors.append(_error(
                "quality.lesson_too_few_exercises",
                f"{manifest.id} 只有 {len(exercises)} 道练习，至少需要 2 道",
                lesson_id=manifest.id,
            ))
        lesson_concepts = set(manifest.concepts)
        for exercise in exercises:
            outside = [
                concept_id
                for concept_id in exercise.concepts
                if concept_id not in lesson_concepts
            ]
            if outside:
                result.errors.append(_error(
                    "quality.exercise_concept_outside_lesson",
                    f"{manifest.id} 的练习 {exercise.id} 引用了本课未声明的概念："
                    + "、".join(outside),
                    lesson_id=manifest.id,
                ))
        if exercises and _max_level(exercises) < _level(manifest.target_level):
            result.errors.append(_error(
                "quality.lesson_level_short",
                f"{manifest.id} 最高练习级别 L{_max_level(exercises)} "
                f"低于目标 {manifest.target_level}",
                lesson_id=manifest.id,
            ))
        if not manifest.resources:
            result.warnings.append(_warning(
                "quality.lesson_no_resource",
                f"{manifest.id} 没有资源",
                lesson_id=manifest.id,
            ))

    for concept_id in concept_ids:
        concept = pack.concepts[concept_id]
        levels = [
            _level(item.level)
            for item in all_exercises
            if concept_id in item.concepts
        ]
        if not levels:
            continue
        best = max(levels)
        if best < _level(concept.target_level):
            result.errors.append(_error(
                "quality.concept_level_short",
                f"概念 {concept_id} 最高练习级别 L{best} "
                f"低于目标 {concept.target_level}",
                concept_id=concept_id,
            ))

    covered_count = len(concept_ids) - len(missing)
    result.metrics.append(QualityMetric(
        "coverage.concepts", "概念有练习",
        proportional(covered_count, len(concept_ids), 15), 15,
        f"{covered_count}/{len(concept_ids)}",
    ))
    enough = sum(1 for lesson in lessons if len(lesson.manifest.exercises) >= 2)
    result.metrics.append(QualityMetric(
        "coverage.lesson_exercises", "每课至少 2 题",
        proportional(enough, len(lessons), 10), 10,
        f"{enough}/{len(lessons)}",
    ))
    types = len({item.type for item in all_exercises})
    result.metrics.append(QualityMetric(
        "coverage.type_variety", "题型多样",
        proportional(min(types, 3), 3, 5), 5,
        f"{types} 种",
    ))
    if types < 3:
        result.warnings.append(_warning(
            "quality.type_variety_low",
            f"全包只有 {types} 种题型，建议至少 3 种",
        ))

    lessons_level_ok = sum(
        1
        for lesson in lessons
        if _max_level(_lesson_exercises(pack, lesson.manifest))
        >= _level(lesson.manifest.target_level)
    )
    result.metrics.append(QualityMetric(
        "level.lessons", "课级达标",
        proportional(lessons_level_ok, len(lessons), 10), 10,
        f"{lessons_level_ok}/{len(lessons)}",
    ))
    concepts_level_ok = sum(
        1
        for concept_id in concept_ids
        if max(
            (
                _level(item.level)
                for item in all_exercises
                if concept_id in item.concepts
            ),
            default=0,
        )
        >= _level(pack.concepts[concept_id].target_level)
    )
    result.metrics.append(QualityMetric(
        "level.concepts", "概念级达标",
        proportional(concepts_level_ok, len(concept_ids), 10), 10,
        f"{concepts_level_ok}/{len(concept_ids)}",
    ))

    objectives_ok = sum(
        1
        for lesson in lessons
        if lesson.manifest.objectives and lesson.manifest.minutes > 0
    )
    result.metrics.append(QualityMetric(
        "structure.objectives", "目标与时长完整",
        proportional(objectives_ok, len(lessons), 5), 5,
        f"{objectives_ok}/{len(lessons)}",
    ))
    resources_ok = sum(1 for lesson in lessons if lesson.manifest.resources)
    result.metrics.append(QualityMetric(
        "structure.lesson_resources", "每课有资源",
        proportional(resources_ok, len(lessons), 5), 5,
        f"{resources_ok}/{len(lessons)}",
    ))
    return result
