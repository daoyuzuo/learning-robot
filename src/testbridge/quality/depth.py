"""Deterministic lesson depth checks.

This module answers "is this lesson substantial enough to teach from?" and is
deliberately separate from the tb/1 contract and the quality score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from testbridge.content.repository import ContentPack

DEFAULT_MIN_CHARS: dict[str, int] = {
    "L1": 1200,
    "L2": 2000,
    "L3": 3500,
    "L4": 4500,
}
DEFAULT_MIN_SECTIONS: dict[str, int] = {
    "L1": 3,
    "L2": 4,
    "L3": 6,
    "L4": 7,
}
DEFAULT_MIN_VISUALS: dict[str, int] = {
    "L1": 0,
    "L2": 0,
    "L3": 1,
    "L4": 1,
}
MIN_EXERCISES = 2

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


class _StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections = 0
        self.tables = 0
        self.figures = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower == "h2":
            self.sections += 1
        elif lower == "table":
            self.tables += 1
        elif lower == "figure":
            self.figures += 1

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)


def body_char_count(body_html: str) -> int:
    """Count non-whitespace characters after removing HTML tags."""
    return len(_WHITESPACE_RE.sub("", _TAG_RE.sub("", body_html)))


def _structure(body_html: str) -> tuple[int, int, int]:
    parser = _StructureParser()
    parser.feed(body_html)
    parser.close()
    return parser.sections, parser.tables, parser.figures


@dataclass(frozen=True)
class DepthIssue:
    code: str
    message: str
    lesson_id: str

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "lesson_id": self.lesson_id,
        }


@dataclass(frozen=True)
class LessonDepth:
    lesson_id: str
    level: str
    chars: int
    sections: int
    tables: int
    figures: int
    exercises: int
    issues: list[DepthIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def as_dict(self) -> dict:
        return {
            "lesson_id": self.lesson_id,
            "level": self.level,
            "chars": self.chars,
            "sections": self.sections,
            "tables": self.tables,
            "figures": self.figures,
            "exercises": self.exercises,
            "ok": self.ok,
            "issues": [issue.as_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class DepthReport:
    lessons: list[LessonDepth] = field(default_factory=list)

    @property
    def errors(self) -> list[DepthIssue]:
        return [issue for lesson in self.lessons for issue in lesson.issues]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "lessons": [lesson.as_dict() for lesson in self.lessons],
            "errors": [issue.as_dict() for issue in self.errors],
        }


def evaluate_depth(pack: ContentPack) -> DepthReport:
    lessons: list[LessonDepth] = []
    for lesson in pack.lessons_in_order():
        manifest = lesson.manifest
        level = manifest.target_level
        chars = body_char_count(lesson.body_html)
        sections, tables, figures = _structure(lesson.body_html)
        exercises = len(manifest.exercises)
        issues: list[DepthIssue] = []

        min_chars = DEFAULT_MIN_CHARS[level]
        if chars < min_chars:
            issues.append(DepthIssue(
                "depth.lesson_too_short",
                f"{chars} < {min_chars}",
                manifest.id,
            ))

        min_sections = DEFAULT_MIN_SECTIONS[level]
        if sections < min_sections:
            issues.append(DepthIssue(
                "depth.too_few_sections",
                f"{sections} < {min_sections}",
                manifest.id,
            ))

        min_visuals = DEFAULT_MIN_VISUALS[level]
        visuals = tables + figures
        if visuals < min_visuals:
            issues.append(DepthIssue(
                "depth.no_table_or_figure",
                f"{visuals} < {min_visuals}",
                manifest.id,
            ))

        if exercises < MIN_EXERCISES:
            issues.append(DepthIssue(
                "depth.too_few_exercises",
                f"{exercises} < {MIN_EXERCISES}",
                manifest.id,
            ))

        lessons.append(LessonDepth(
            lesson_id=manifest.id,
            level=level,
            chars=chars,
            sections=sections,
            tables=tables,
            figures=figures,
            exercises=exercises,
            issues=issues,
        ))
    return DepthReport(lessons=lessons)
