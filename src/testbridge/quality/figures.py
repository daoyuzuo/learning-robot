"""Figure coverage and unresolved-mount checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from testbridge.content.repository import ContentPack
from testbridge.quality.report import QualityIssue

FIGURE_RE = re.compile(r"<figure\b", re.IGNORECASE)
MIN_FIGURE_VERSION = 4


@dataclass
class FigureResult:
    errors: list[QualityIssue] = field(default_factory=list)
    warnings: list[QualityIssue] = field(default_factory=list)


class _MountScanner(HTMLParser):
    """Count real ``div`` mount tags, ignoring prose or code that quotes them."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.mounts = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "div":
            return
        for name, value in attrs:
            if name.lower() == "data-tb-figure" and value and value.strip():
                self.mounts += 1
                return

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def _unresolved_mounts(body: str) -> int:
    scanner = _MountScanner()
    scanner.feed(body)
    scanner.close()
    return scanner.mounts


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
        if _unresolved_mounts(body):
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
        if not FIGURE_RE.search(body):
            result.warnings.append(QualityIssue(
                code="quality.lesson_no_figure",
                message=f"{lesson_id} 没有图示",
                severity="warning",
                lesson_id=lesson_id,
            ))
    return result
