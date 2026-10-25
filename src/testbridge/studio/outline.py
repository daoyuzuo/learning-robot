"""Outline parsing, HTML rendering, and contract file writing."""

from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

import yaml

from testbridge.contract.sanitize import sanitize_fragment
from testbridge.studio.store import ID_RE, DraftStore

MAX_CONCEPTS = 12
MAX_MODULES = 3
MAX_LESSONS_PER_MODULE = 5
CONCEPT_FIELDS = (
    "id", "title", "domain", "target_level", "prerequisites", "related",
    "weight", "evidence_criteria", "resources",
)
LEVELS = {"L1", "L2", "L3", "L4"}


class OutlineError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class LessonPlan:
    lesson_id: str
    title: str
    minutes: int
    objectives: list[str]
    queries: list[str]
    module_id: str = "M01"
    concepts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ModulePlan:
    module_id: str
    title: str
    concepts: list[str] | None
    lessons: list[LessonPlan]


def _check_id(value: object, label: str) -> None:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise OutlineError(f"{label} 不是合法 ID：{value!r}")


def parse_outline_json(
    raw: str, module_count: int, lessons_per_module: int
) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OutlineError(f"大纲不是合法 JSON：{exc.msg}") from None
    if not isinstance(data, dict):
        raise OutlineError("大纲必须是 JSON 对象")

    pack_title = data.get("pack_title") or data.get("module_title")
    if not isinstance(pack_title, str) or not pack_title.strip():
        raise OutlineError("缺少 pack_title")

    concepts = data.get("concepts")
    if not isinstance(concepts, list) or not 1 <= len(concepts) <= MAX_CONCEPTS:
        raise OutlineError("concepts 数量必须在 1–12 之间")
    concept_ids = []
    for concept in concepts:
        if not isinstance(concept, dict):
            raise OutlineError("concept 必须是对象")
        _check_id(concept.get("id"), "concept.id")
        concept_ids.append(concept["id"])
        if not isinstance(concept.get("title"), str) or not concept["title"].strip():
            raise OutlineError(f"{concept['id']} 缺少 title")
        if concept.get("target_level") not in LEVELS:
            raise OutlineError(f"{concept['id']} 的 target_level 必须是 L1–L4")
        for criterion in concept.get("evidence_criteria") or []:
            if not isinstance(criterion, dict):
                raise OutlineError(f"{concept['id']} 的 evidence_criteria 必须是对象")
            _check_id(criterion.get("id"), "evidence_criteria.id")
            if criterion.get("level") not in LEVELS:
                raise OutlineError(f"{criterion['id']} 的 level 必须是 L1–L4")
    if len(set(concept_ids)) != len(concept_ids):
        raise OutlineError("concept.id 必须唯一")
    for concept in concepts:
        for item in concept.get("prerequisites") or []:
            if item not in concept_ids:
                raise OutlineError(f"先修概念不存在：{item}")

    raw_modules = data.get("modules")
    legacy = False
    if raw_modules is None:
        raw_lessons = data.get("lessons")
        if not isinstance(raw_lessons, list):
            raise OutlineError("缺少 modules 或 lessons")
        legacy = True
        raw_modules = [{
            "id": "M01", "title": pack_title,
            "concepts": list(concept_ids), "lessons": raw_lessons,
        }]

    if not isinstance(raw_modules, list) or len(raw_modules) != module_count:
        raise OutlineError(f"模块数量必须是 {module_count}")
    if not 1 <= module_count <= MAX_MODULES:
        raise OutlineError("模块数量必须在 1–3 之间")
    if not 1 <= lessons_per_module <= MAX_LESSONS_PER_MODULE:
        raise OutlineError("每模块课数必须在 1–5 之间")

    module_ids: list[str] = []
    lesson_ids: list[str] = []
    modules: list[dict] = []
    for module in raw_modules:
        if not isinstance(module, dict):
            raise OutlineError("module 必须是对象")
        _check_id(module.get("id"), "module.id")
        module_ids.append(module["id"])
        title = module.get("title")
        if not isinstance(title, str) or not title.strip():
            raise OutlineError(f"{module['id']} 缺少 title")
        module_concepts = module.get("concepts")
        if not isinstance(module_concepts, list) or not module_concepts:
            raise OutlineError(f"{module['id']} 必须声明至少 1 个概念")
        for concept_id in module_concepts:
            if concept_id not in concept_ids:
                raise OutlineError(f"{module['id']} 引用了不存在的概念：{concept_id}")
        raw_lessons = module.get("lessons")
        if not isinstance(raw_lessons, list) or len(raw_lessons) != lessons_per_module:
            raise OutlineError(f"{module['id']} 课程数量必须是 {lessons_per_module}")
        normalized_lessons = []
        covered: set[str] = set()
        for lesson in raw_lessons:
            if not isinstance(lesson, dict):
                raise OutlineError("lesson 必须是对象")
            _check_id(lesson.get("id"), "lesson.id")
            lesson_ids.append(lesson["id"])
            if not lesson.get("objectives"):
                raise OutlineError(f"{lesson['id']} 缺少 objectives")
            minutes = lesson.get("minutes")
            if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes <= 0:
                raise OutlineError(f"{lesson['id']} 的 minutes 必须是正整数")
            lesson_concepts = list(module_concepts) if legacy else lesson.get("concepts")
            if not isinstance(lesson_concepts, list) or not lesson_concepts:
                raise OutlineError(f"{lesson['id']} 必须声明至少 1 个概念")
            for concept_id in lesson_concepts:
                if concept_id not in module_concepts:
                    raise OutlineError(
                        f"{lesson['id']} 的概念不属于模块 {module['id']}：{concept_id}"
                    )
                covered.add(concept_id)
            normalized_lessons.append({
                **lesson,
                "concepts": [str(item) for item in lesson_concepts],
            })
        missing = [item for item in module_concepts if item not in covered]
        if missing:
            raise OutlineError(
                f"{module['id']} 的概念没有被任何课覆盖：{missing}"
            )
        modules.append({**module, "lessons": normalized_lessons})

    if len(set(module_ids)) != len(module_ids):
        raise OutlineError("module.id 必须唯一")
    if len(set(lesson_ids)) != len(lesson_ids):
        raise OutlineError("lesson.id 必须唯一")
    return {
        "pack_title": pack_title,
        "module_title": pack_title,
        "concepts": concepts,
        "modules": modules,
        "lessons": [
            lesson for module in modules for lesson in module["lessons"]
        ],
    }


def render_outline_html(module_title: str, lessons: list[LessonPlan]) -> str:
    sections = []
    for plan in lessons:
        objectives = "".join(
            f"<li>{html_lib.escape(item)}</li>" for item in plan.objectives
        )
        queries = "".join(
            f"<li>{html_lib.escape(item)}</li>" for item in plan.queries
        )
        sections.append(
            f'<section class="tb-outline-lesson" id="{html_lib.escape(plan.lesson_id)}">'
            f"<h2>{html_lib.escape(plan.title)}</h2>"
            f'<p class="tb-minutes">{plan.minutes}</p>'
            f'<ul class="tb-objectives">{objectives}</ul>'
            f'<ul class="tb-queries">{queries}</ul>'
            "</section>"
        )
    return (
        '<article class="tb-outline">'
        f'<h1 class="tb-module-title">{html_lib.escape(module_title)}</h1>'
        + "".join(sections)
        + "</article>"
    )


class _OutlineParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.module_title = ""
        self.lessons: list[dict] = []
        self._current: dict | None = None
        self._capture: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "section" and "tb-outline-lesson" in classes:
            self._current = {
                "id": values.get("id") or "", "title": "", "minutes": 20,
                "objectives": [], "queries": [],
            }
        elif tag == "h1" and "tb-module-title" in classes:
            self._capture = "title"
            self._buffer = []
        elif tag == "h2" and self._current is not None:
            self._capture = "lesson_title"
            self._buffer = []
        elif tag == "p" and "tb-minutes" in classes:
            self._capture = "minutes"
            self._buffer = []
        elif tag == "ul" and self._current is not None:
            self._capture = (
                "objectives" if "tb-objectives" in classes
                else "queries" if "tb-queries" in classes else None
            )
        elif tag == "li" and self._capture in {"objectives", "queries"}:
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self._capture == "title":
            self.module_title = "".join(self._buffer).strip()
            self._capture = None
        elif tag == "h2" and self._capture == "lesson_title" and self._current is not None:
            self._current["title"] = "".join(self._buffer).strip()
            self._capture = None
        elif tag == "p" and self._capture == "minutes" and self._current is not None:
            try:
                self._current["minutes"] = int("".join(self._buffer).strip())
            except ValueError:
                self._current["minutes"] = 20
            self._capture = None
        elif tag == "li" and self._capture in {"objectives", "queries"}:
            value = "".join(self._buffer).strip()
            if value and self._current is not None:
                self._current[self._capture].append(value)
            self._buffer = []
        elif tag == "ul":
            self._capture = None
        elif tag == "section" and self._current is not None:
            self.lessons.append(self._current)
            self._current = None

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)


def parse_outline_html(html: str) -> list[LessonPlan]:
    parser = _OutlineParser()
    parser.feed(html)
    parser.close()
    plans = []
    seen: set[str] = set()
    for item in parser.lessons:
        _check_id(item["id"], "lesson.id")
        if item["id"] in seen:
            raise OutlineError(f"课程 ID 重复：{item['id']}")
        seen.add(item["id"])
        plans.append(LessonPlan(
            lesson_id=item["id"],
            title=item["title"] or item["id"],
            minutes=item["minutes"] or 20,
            objectives=item["objectives"],
            queries=item["queries"],
        ))
    if not plans:
        raise OutlineError("大纲里没有找到课程")
    return plans


def lesson_plans(parsed: dict) -> list[LessonPlan]:
    plans: list[LessonPlan] = []
    for module in parsed["modules"]:
        for item in module["lessons"]:
            plans.append(LessonPlan(
                lesson_id=item["id"],
                title=str(item.get("title") or item["id"]),
                minutes=int(item.get("minutes") or 20),
                objectives=[str(value) for value in item.get("objectives") or []],
                queries=[str(value) for value in item.get("research_queries") or []],
                module_id=module["id"],
                concepts=[str(value) for value in item.get("concepts") or []],
            ))
    return plans


def write_outline(store: DraftStore, draft_id: str, parsed: dict) -> list[LessonPlan]:
    draft = store.load(draft_id)
    lessons = lesson_plans(parsed)
    concepts = [
        {key: value for key, value in item.items() if key in CONCEPT_FIELDS}
        for item in parsed["concepts"]
    ]

    pack = {
        "schema": "tb/1",
        "id": draft_id,
        "version": "0.1.0",
        "title": parsed["module_title"],
        "description": draft["topic"],
        "language": "zh-CN",
        "license": "CC-BY-4.0",
        "authors": ["studio"],
        "created": draft["created_at"][:10],
        "fixture": False,
    }
    module = {
        "schema": "tb/1",
        "id": "M01",
        "title": parsed["module_title"],
        "priority": "P1",
        "concepts": [item["id"] for item in concepts],
        "lessons": [plan.lesson_id for plan in lessons],
        "order": 1,
    }

    store.write(draft_id, "pack.yaml", yaml.safe_dump(
        pack, allow_unicode=True, sort_keys=False))
    store.write(draft_id, "concepts.yaml", yaml.safe_dump(
        {"schema": "tb/1", "concepts": concepts},
        allow_unicode=True, sort_keys=False))
    store.write(draft_id, "modules/M01/module.yaml", yaml.safe_dump(
        module, allow_unicode=True, sort_keys=False))
    store.write(
        draft_id, "outline.html",
        sanitize_fragment(render_outline_html(parsed["module_title"], lessons)),
    )

    research_defaults = {
        "status": "pending", "error": None, "at": None, "queries": 0, "hits": 0,
    }
    lesson_defaults = {"status": "pending", "error": None, "at": None}
    for step, defaults in (
        ("research", research_defaults), ("lessons", lesson_defaults),
    ):
        container = draft["steps"][step]
        draft["steps"][step] = {
            plan.lesson_id: container.get(plan.lesson_id, dict(defaults))
            for plan in lessons
        }
    store.save(draft)
    return lessons
