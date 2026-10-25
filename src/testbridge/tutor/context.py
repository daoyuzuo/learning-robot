"""Build a grounded context for one lesson, without exercise answers."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from testbridge.content.repository import ContentPack

MAX_CONTEXT_CHARS = 12000

_SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.IGNORECASE | re.DOTALL)
_SECTION_RE = re.compile(r"<section\b[^>]*>(.*?)</section>", re.IGNORECASE | re.DOTALL)
_HEADING_RE = re.compile(r"<h([1-4])\b[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _plain(fragment: str) -> str:
    return _SPACE_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", fragment))).strip()


@dataclass(frozen=True)
class TutorContext:
    lesson_id: str
    title: str
    text: str
    headings: list[str]
    resource_ids: list[str]


def _sections(body: str) -> list[str]:
    chunks = []
    for fragment in _SECTION_RE.findall(body):
        text = _plain(fragment)
        if text:
            chunks.append(text)
    return chunks


def _headings(body: str) -> list[str]:
    return [
        text
        for text in (_plain(match.group(2)) for match in _HEADING_RE.finditer(body))
        if text
    ]


def build_context(pack: ContentPack, lesson_id: str) -> TutorContext:
    lesson = pack.lesson(lesson_id)
    manifest = lesson.manifest
    body = _SCRIPT_RE.sub(" ", lesson.body_html)

    parts = [
        f"课程：{manifest.title}（目标 {manifest.target_level}，{manifest.minutes} 分钟）",
        "目标：" + "；".join(manifest.objectives),
    ]

    concept_lines = []
    for concept_id in manifest.concepts:
        concept = pack.concepts.get(concept_id)
        if concept is None:
            continue
        criteria = "；".join(item.description for item in concept.evidence_criteria)
        concept_lines.append(
            f"- {concept.title}（目标 {concept.target_level}）：{criteria}"
        )
    if concept_lines:
        parts.append("概念：\n" + "\n".join(concept_lines))

    exercise_lines = []
    for exercise_id in manifest.exercises:
        exercise = pack.exercises.get(exercise_id)
        if exercise is None:
            continue
        options = " ".join(f"{option.id}. {option.text}" for option in exercise.options)
        suffix = f" 选项：{options}" if options else ""
        exercise_lines.append(f"- {exercise.prompt}{suffix}")
    if exercise_lines:
        parts.append("练习（仅题干与选项）：\n" + "\n".join(exercise_lines))

    resource_lines = []
    for resource_id in manifest.resources:
        resource = pack.resources.get(resource_id)
        if resource is None:
            continue
        resource_lines.append(
            f"- {resource.id} {resource.title}：{resource.why}（{resource.url}）"
        )
    if resource_lines:
        parts.append("资源：\n" + "\n".join(resource_lines))

    header = "\n\n".join(parts)
    sections = _sections(body)
    budget = MAX_CONTEXT_CHARS - len(header) - len("\n\n正文：\n")
    kept: list[str] = []
    total = 0
    for section in sections:
        if total + len(section) + 1 > budget:
            break
        kept.append(section)
        total += len(section) + 1

    text = header + "\n\n正文：\n" + "\n".join(kept)
    if len(kept) < len(sections):
        text += "\n（正文已截断）"

    return TutorContext(
        lesson_id=manifest.id,
        title=manifest.title,
        text=text,
        headings=_headings(body),
        resource_ids=list(manifest.resources),
    )
