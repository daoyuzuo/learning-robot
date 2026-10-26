"""Load validated content packs and provide read-only queries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from testbridge.contract.loader import ContentError, load_lesson_file, load_model
from testbridge.contract.models import (
    Concept,
    ConceptsFile,
    Exercise,
    ExercisesFile,
    LessonManifest,
    Module,
    PackMeta,
    Resource,
    ResourcesFile,
    Widget,
    WidgetsFile,
)
from testbridge.contract.validator import ValidationReport, validate_pack


KIND_BY_TYPE = {
    "paper": "paper",
    "standard": "standard",
    "standard_draft": "standard",
    "docs": "official_docs",
    "documentation": "official_docs",
    "official-doc": "official_docs",
    "official_docs": "official_docs",
    "repository": "repository",
    "article": "engineering_blog",
    "blog": "engineering_blog",
    "tutorial": "tutorial",
}


def _explicit_kind_ids(path: Path) -> set[str]:
    """Resource ids whose YAML explicitly sets ``kind``."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return set()
    if not isinstance(data, dict):
        return set()
    ids: set[str] = set()
    for item in data.get("resources") or []:
        if not isinstance(item, dict) or "kind" not in item:
            continue
        resource_id = item.get("id")
        if isinstance(resource_id, str):
            ids.add(resource_id)
    return ids


class ContentValidationError(Exception):
    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        super().__init__(f"content pack has {len(report.errors)} error(s)")


@dataclass(frozen=True)
class Lesson:
    manifest: LessonManifest
    body_html: str
    path: Path


@dataclass(frozen=True)
class ContentPack:
    root: Path
    meta: PackMeta
    concepts: dict[str, Concept]
    exercises: dict[str, Exercise]
    resources: dict[str, Resource]
    widgets: dict[str, Widget]
    modules: dict[str, Module]
    lessons: dict[str, Lesson]

    def concept(self, concept_id: str) -> Concept:
        return self.concepts[concept_id]

    def lesson(self, lesson_id: str) -> Lesson:
        return self.lessons[lesson_id]

    def exercise(self, exercise_id: str) -> Exercise:
        return self.exercises[exercise_id]

    def resource(self, resource_id: str) -> Resource:
        return self.resources[resource_id]

    def widget(self, widget_id: str) -> Widget:
        return self.widgets[widget_id]

    def lessons_in_order(self) -> list[Lesson]:
        ordered: list[Lesson] = []
        for module in sorted(self.modules.values(), key=lambda item: (item.order, item.id)):
            for lesson_id in module.lessons:
                if lesson_id in self.lessons:
                    ordered.append(self.lessons[lesson_id])
        return ordered

    def prev_next(self, lesson_id: str) -> tuple[Lesson | None, Lesson | None]:
        ordered = self.lessons_in_order()
        for index, lesson in enumerate(ordered):
            if lesson.manifest.id == lesson_id:
                prev_lesson = ordered[index - 1] if index > 0 else None
                next_lesson = ordered[index + 1] if index + 1 < len(ordered) else None
                return prev_lesson, next_lesson
        return None, None


@dataclass(frozen=True)
class PackInfo:
    path: Path
    meta: PackMeta


def load_pack(pack_dir: Path) -> ContentPack:
    report = validate_pack(pack_dir)
    if not report.ok:
        raise ContentValidationError(report)

    meta = load_model(pack_dir / "pack.yaml", PackMeta)
    concepts_file = load_model(pack_dir / "concepts.yaml", ConceptsFile)
    exercises_file = load_model(pack_dir / "exercises.yaml", ExercisesFile)
    resources_path = pack_dir / "resources.yaml"
    widgets_path = pack_dir / "widgets.yaml"
    resources_file = (
        load_model(resources_path, ResourcesFile)
        if resources_path.is_file()
        else ResourcesFile(schema="tb/1", resources=[])
    )
    widgets_file = (
        load_model(widgets_path, WidgetsFile)
        if widgets_path.is_file()
        else WidgetsFile(schema="tb/1", widgets=[])
    )

    modules: dict[str, Module] = {}
    lessons: dict[str, Lesson] = {}
    for module_path in sorted((pack_dir / "modules").glob("*/module.yaml")):
        module = load_model(module_path, Module)
        modules[module.id] = module
        for lesson_id in module.lessons:
            path = module_path.parent / "lessons" / f"{lesson_id}.html"
            manifest, body = load_lesson_file(path)
            lessons[lesson_id] = Lesson(manifest=manifest, body_html=body, path=path)

    resources = {item.id: item for item in resources_file.resources}
    if resources_path.is_file():
        explicit = _explicit_kind_ids(resources_path)
        for resource_id, resource in list(resources.items()):
            if resource_id in explicit:
                continue
            mapped = KIND_BY_TYPE.get(resource.type.strip().lower())
            if mapped and mapped != resource.kind:
                resources[resource_id] = resource.model_copy(
                    update={"kind": mapped}
                )

    return ContentPack(
        root=pack_dir,
        meta=meta,
        concepts={item.id: item for item in concepts_file.concepts},
        exercises={item.id: item for item in exercises_file.exercises},
        resources=resources,
        widgets={item.id: item for item in widgets_file.widgets},
        modules=modules,
        lessons=lessons,
    )


def list_packs(root: Path) -> list[PackInfo]:
    infos: list[PackInfo] = []
    for pack_yaml in sorted(root.glob("*/pack.yaml")):
        try:
            meta = load_model(pack_yaml, PackMeta)
        except ContentError:
            continue
        infos.append(PackInfo(path=pack_yaml.parent, meta=meta))
    return infos
