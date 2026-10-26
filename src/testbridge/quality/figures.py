"""Figure coverage and unresolved-mount checks."""

from __future__ import annotations

from dataclasses import dataclass, field

from testbridge.content.repository import ContentPack
from testbridge.quality.report import QualityIssue

MOUNT_MARKER = "data-tb-figure"
FIGURE_MARKER = "<figure"
MIN_FIGURE_VERSION = 4


@dataclass
class FigureResult:
    errors: list[QualityIssue] = field(default_factory=list)
    warnings: list[QualityIssue] = field(default_factory=list)


def _version_number(version: str) -> int:
    prefix, _, suffix = version.partition("/")
    if prefix != "studio":
        return 0
    try:
        return int(suffix)
    except ValueError:
        return 0


def evaluate_figures(
    pack: ContentPack, prompt_versions: dict[str, str]
) -> FigureResult:
    result = FigureResult()
    for lesson in pack.lessons_in_order():
        lesson_id = lesson.manifest.id
        body = lesson.body_html
        if MOUNT_MARKER in body:
            result.errors.append(QualityIssue(
                code="quality.figure_mount_unresolved",
                message=f"{lesson_id} 仍有未解析的图形挂载点",
                severity="error",
                lesson_id=lesson_id,
            ))
            continue
        version = prompt_versions.get(lesson_id, "")
        if _version_number(version) < MIN_FIGURE_VERSION:
            continue
        if FIGURE_MARKER not in body:
            result.warnings.append(QualityIssue(
                code="quality.lesson_no_figure",
                message=f"{lesson_id} 没有图示",
                severity="warning",
                lesson_id=lesson_id,
            ))
    return result
