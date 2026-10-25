"""Outline parsing, HTML rendering, and contract file writing."""

from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

import yaml

from testbridge.contract.sanitize import sanitize_fragment
from testbridge.studio.store import (
    ID_RE,
    MAX_LESSONS_PER_MODULE,
    MAX_MODULES,
    DraftStore,
)

MAX_CONCEPTS = 12
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
        raise OutlineError("缺少 pack_title 或 module_title")

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

    if not 1 <= module_count <= MAX_MODULES:
        raise OutlineError("模块数量必须在 1–3 之间")
    if not 1 <= lessons_per_module <= MAX_LESSONS_PER_MODULE:
        raise OutlineError("每模块课数必须在 1–5 之间")
    if not isinstance(raw_modules, list) or len(raw_modules) != module_count:
        raise OutlineError(f"模块数量必须是 {module_count}")

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
            objectives = lesson.get("objectives")
            if not isinstance(objectives, list) or not objectives:
                raise OutlineError(f"{lesson['id']} 缺少 objectives")
            for name in ("exercise_intents", "research_queries"):
                value = lesson.get(name)
                if value is not None and not isinstance(value, list):
                    raise OutlineError(f"{lesson['id']} 的 {name} 必须是数组")
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


def render_outline_html(pack_title: str, modules: list[ModulePlan]) -> str:
    parts = [
        (
            '<article class="tb-outline">'
            f'<h1 class="tb-pack-title">{html_lib.escape(pack_title)}</h1>'
        )
    ]
    for module in modules:
        parts.append(
            f'<section class="tb-outline-module" id="{html_lib.escape(module.module_id)}">'
            f'<h2 class="tb-module-title">{html_lib.escape(module.title)}</h2>'
        )
        if module.concepts is not None:
            items = "".join(
                f"<li>{html_lib.escape(item)}</li>" for item in module.concepts
            )
            parts.append(f'<ul class="tb-module-concepts">{items}</ul>')
        for lesson in module.lessons:
            parts.append(
                f'<section class="tb-outline-lesson" id="{html_lib.escape(lesson.lesson_id)}">'
                f'<h3 class="tb-lesson-title">{html_lib.escape(lesson.title)}</h3>'
                f'<p class="tb-minutes">{lesson.minutes}</p>'
            )
            if lesson.concepts:
                items = "".join(
                    f"<li>{html_lib.escape(item)}</li>" for item in lesson.concepts
                )
                parts.append(f'<ul class="tb-lesson-concepts">{items}</ul>')
            objectives = "".join(
                f"<li>{html_lib.escape(item)}</li>" for item in lesson.objectives
            )
            queries = "".join(
                f"<li>{html_lib.escape(item)}</li>" for item in lesson.queries
            )
            parts.append(
                f'<ul class="tb-objectives">{objectives}</ul>'
                f'<ul class="tb-queries">{queries}</ul>'
                "</section>"
            )
        parts.append("</section>")
    parts.append("</article>")
    return "".join(parts)


class _OutlineParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pack_title = ""
        self.modules: list[dict] = []
        self.legacy_lessons: list[dict] = []
        self._module: dict | None = None
        self._lesson: dict | None = None
        self._capture: str | None = None
        self._buffer: list[str] = []
        self._items: str | None = None
        self._concepts_seen = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "h1" and (
            "tb-pack-title" in classes
            or ("tb-module-title" in classes and self._module is None)
        ):
            self._capture = "pack_title"
            self._buffer = []
        elif tag == "section" and "tb-outline-module" in classes:
            self._module = {
                "id": values.get("id") or "", "title": "",
                "concepts": [], "lessons": [],
            }
            self.modules.append(self._module)
            self._concepts_seen = False
        elif tag == "h2" and "tb-module-title" in classes and self._module:
            self._capture = "module_title"
            self._buffer = []
        elif tag == "section" and "tb-outline-lesson" in classes:
            self._lesson = {
                "id": values.get("id") or "", "title": "", "minutes": 20,
                "objectives": [], "queries": [], "concepts": [],
            }
        elif tag in {"h2", "h3"} and self._lesson is not None:
            self._capture = "lesson_title"
            self._buffer = []
        elif tag == "p" and "tb-minutes" in classes and self._lesson is not None:
            self._capture = "minutes"
            self._buffer = []
        elif tag == "ul" and "tb-module-concepts" in classes and self._module:
            self._module["concepts"] = []
            self._concepts_seen = True
            self._items = "module_concepts"
        elif tag == "ul" and "tb-lesson-concepts" in classes and self._lesson:
            self._lesson["concepts"] = []
            self._items = "lesson_concepts"
        elif tag == "ul" and "tb-objectives" in classes and self._lesson:
            self._items = "objectives"
        elif tag == "ul" and "tb-queries" in classes and self._lesson:
            self._items = "queries"
        elif tag == "li" and self._items:
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h1", "h2", "h3"} and self._capture in {
            "pack_title", "module_title", "lesson_title",
        }:
            value = "".join(self._buffer).strip()
            if self._capture == "pack_title":
                self.pack_title = value
            elif self._capture == "module_title" and self._module is not None:
                self._module["title"] = value
            elif self._capture == "lesson_title" and self._lesson is not None:
                self._lesson["title"] = value
            self._capture = None
        elif tag == "p" and self._capture == "minutes" and self._lesson is not None:
            try:
                self._lesson["minutes"] = int("".join(self._buffer).strip())
            except ValueError:
                self._lesson["minutes"] = 20
            self._capture = None
        elif tag == "li" and self._items:
            value = "".join(self._buffer).strip()
            if value:
                if self._items == "module_concepts" and self._module is not None:
                    self._module["concepts"].append(value)
                elif self._items == "lesson_concepts" and self._lesson is not None:
                    self._lesson["concepts"].append(value)
                elif self._lesson is not None and self._items in {"objectives", "queries"}:
                    self._lesson[self._items].append(value)
            self._buffer = []
        elif tag == "ul":
            self._items = None
        elif tag == "section" and self._lesson is not None:
            target = self._module["lessons"] if self._module else self.legacy_lessons
            target.append(self._lesson)
            self._lesson = None
        elif tag == "section" and self._module is not None:
            if not self._concepts_seen:
                self._module["concepts"] = None
            self._module = None

    def handle_data(self, data: str) -> None:
        if self._capture or self._items:
            self._buffer.append(data)


def parse_outline_html(html: str) -> list[ModulePlan]:
    parser = _OutlineParser()
    parser.feed(html)
    parser.close()
    raw_modules = parser.modules
    if raw_modules and parser.legacy_lessons:
        raise OutlineError("课程必须位于模块 section 内")
    if not raw_modules:
        raw_modules = [{
            "id": "M01",
            "title": parser.pack_title or "M01",
            "concepts": None,
            "lessons": parser.legacy_lessons,
        }]
    modules: list[ModulePlan] = []
    module_seen: set[str] = set()
    lesson_seen: set[str] = set()
    for raw in raw_modules:
        _check_id(raw["id"], "module.id")
        if raw["id"] in module_seen:
            raise OutlineError(f"模块 ID 重复：{raw['id']}")
        module_seen.add(raw["id"])
        raw_lessons = raw.get("lessons") or []
        lessons = []
        for item in raw_lessons:
            _check_id(item["id"], "lesson.id")
            if item["id"] in lesson_seen:
                raise OutlineError(f"课程 ID 重复：{item['id']}")
            lesson_seen.add(item["id"])
            lessons.append(LessonPlan(
                lesson_id=item["id"],
                title=item["title"] or item["id"],
                minutes=item["minutes"] or 20,
                objectives=item["objectives"],
                queries=item["queries"],
                module_id=raw["id"],
                concepts=item.get("concepts") or [],
            ))
        modules.append(ModulePlan(
            module_id=raw["id"],
            title=raw["title"] or raw["id"],
            concepts=raw.get("concepts"),
            lessons=lessons,
        ))
    if not lesson_seen:
        raise OutlineError("大纲里没有找到课程")
    return modules


def flatten_modules(modules: list[ModulePlan]) -> list[LessonPlan]:
    return [lesson for module in modules for lesson in module.lessons]


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


def write_module_files(
    store: DraftStore, draft_id: str, modules: list[ModulePlan]
) -> None:
    root = store.path(draft_id) / "modules"
    existing = {
        path.parent.name for path in root.glob("*/module.yaml")
    } if root.is_dir() else set()
    for index, module in enumerate(modules, start=1):
        path = root / module.module_id / "module.yaml"
        if module.concepts is None:
            data = (
                yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                if path.is_file()
                else {"concepts": []}
            )
        else:
            data = {
                "schema": "tb/1", "id": module.module_id,
                "title": module.title, "priority": "P1",
                "concepts": module.concepts,
            }
        data["title"] = module.title
        data["lessons"] = [lesson.lesson_id for lesson in module.lessons]
        data["order"] = index
        data.setdefault("schema", "tb/1")
        data.setdefault("id", module.module_id)
        data.setdefault("priority", "P1")
        data.setdefault("concepts", [])
        store.write(
            draft_id, f"modules/{module.module_id}/module.yaml",
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        )
    current = {module.module_id for module in modules}
    for module_id in sorted(existing - current):
        path = root / module_id / "module.yaml"
        if path.is_file():
            path.replace(path.with_suffix(".yaml.removed"))


def _rekey_steps(
    store: DraftStore, draft_id: str, modules: list[ModulePlan]
) -> None:
    lessons = flatten_modules(modules)
    research_defaults = {
        "status": "pending", "error": None, "at": None,
        "queries": 0, "hits": 0, "backend": "",
    }
    lesson_defaults = {"status": "pending", "error": None, "at": None}

    def rekey(draft: dict) -> None:
        # Re-check under the store lock: a batch may have started after the
        # caller's own guard, and resetting its step would corrupt progress.
        if draft["steps"].get("batch", {}).get("status") == "running":
            raise OutlineError("批量运行中，不能保存大纲")
        for step, defaults in (
            ("research", research_defaults), ("lessons", lesson_defaults),
        ):
            container = draft["steps"][step]
            draft["steps"][step] = {
                lesson.lesson_id: container.get(lesson.lesson_id, dict(defaults))
                for lesson in lessons
            }
        draft["steps"]["batch"] = {
            "status": "pending", "error": None, "at": None,
            "mode": None, "done": 0, "total": 0,
        }

    store.update(draft_id, rekey)


def write_outline(
    store: DraftStore, draft_id: str, parsed: dict
) -> list[ModulePlan]:
    draft = store.load(draft_id)
    modules = [
        ModulePlan(
            module_id=module["id"],
            title=module["title"],
            concepts=[str(item) for item in module["concepts"]],
            lessons=[
                LessonPlan(
                    lesson_id=item["id"],
                    title=str(item.get("title") or item["id"]),
                    minutes=int(item.get("minutes") or 20),
                    objectives=[str(value) for value in item.get("objectives") or []],
                    queries=[
                        str(value) for value in item.get("research_queries") or []
                    ],
                    module_id=module["id"],
                    concepts=[str(value) for value in item.get("concepts") or []],
                )
                for item in module["lessons"]
            ],
        )
        for module in parsed["modules"]
    ]
    concepts = [
        {key: value for key, value in item.items() if key in CONCEPT_FIELDS}
        for item in parsed["concepts"]
    ]
    pack = {
        "schema": "tb/1", "id": draft_id, "version": "0.1.0",
        "title": parsed["pack_title"], "description": draft["topic"],
        "language": "zh-CN", "license": "CC-BY-4.0", "authors": ["studio"],
        "created": draft["created_at"][:10], "fixture": False,
    }
    store.write(draft_id, "pack.yaml", yaml.safe_dump(
        pack, allow_unicode=True, sort_keys=False))
    store.write(draft_id, "concepts.yaml", yaml.safe_dump(
        {"schema": "tb/1", "concepts": concepts},
        allow_unicode=True, sort_keys=False))
    write_module_files(store, draft_id, modules)
    store.write(
        draft_id, "outline.html",
        sanitize_fragment(render_outline_html(parsed["pack_title"], modules)),
    )
    _rekey_steps(store, draft_id, modules)
    return modules


def save_outline_html(
    store: DraftStore, draft_id: str, html: str
) -> list[ModulePlan]:
    clean = sanitize_fragment(html)
    modules = parse_outline_html(clean)
    try:
        concepts_file = yaml.safe_load(store.read(draft_id, "concepts.yaml")) or {}
    except FileNotFoundError:
        concepts_file = {}
    concept_ids = {
        item.get("id") for item in concepts_file.get("concepts") or []
    }
    for module in modules:
        if module.concepts is None:
            continue
        missing = [item for item in module.concepts if item not in concept_ids]
        if missing:
            raise OutlineError(f"模块 {module.module_id} 引用不存在的概念：{missing}")
    store.write(draft_id, "outline.html", clean)
    write_module_files(store, draft_id, modules)
    _rekey_steps(store, draft_id, modules)
    return modules
