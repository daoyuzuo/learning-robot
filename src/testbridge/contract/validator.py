"""Semantic validation for tb/1 content packs."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from .loader import ContentError, load_lesson_file, load_model
from .models import (
    ConceptsFile,
    ExercisesFile,
    LessonManifest,
    Module,
    PackMeta,
    ResourcesFile,
    WidgetsFile,
)
from .sanitize import find_forbidden_html, sanitize_fragment


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    path: str = ""


@dataclass
class ValidationReport:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _load(path: Path, model, report: ValidationReport):
    try:
        return load_model(path, model)
    except ContentError as exc:
        report.errors.append(Issue("load.invalid", str(exc), str(path)))
        return None


def find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    state: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for nxt in graph.get(node, []):
            if state.get(nxt, 0) == 0:
                visit(nxt)
            elif state.get(nxt) == 1:
                cycles.append(stack[stack.index(nxt) :] + [nxt])
        stack.pop()
        state[node] = 2

    for node in graph:
        if state.get(node, 0) == 0:
            visit(node)
    return cycles


@dataclass
class _Mount:
    attribute: str
    value: str
    tag: str
    self_closing: bool = False
    has_content: bool = False
    closed: bool = False


class _MountRefParser(HTMLParser):
    """Collect exercise/widget mounts from attributes only.

    Text nodes (including escaped markup shown inside ``code``) and comments are
    ignored by HTMLParser, and attribute values are entity-decoded regardless of
    quoting style. Mounts are tracked through their element lifetime so callers
    can enforce the empty-``<div>`` contract.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.exercise_ids: list[str] = []
        self.widget_ids: list[str] = []
        self.mounts: list[_Mount] = []
        self._frames: list[tuple[str, list[_Mount]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._mark_content()
        self._frames.append((tag.lower(), self._collect(tag, attrs)))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._mark_content()
        for mount in self._collect(tag, attrs):
            mount.self_closing = True
            mount.closed = True

    def handle_endtag(self, tag: str) -> None:
        lower_tag = tag.lower()
        for index in range(len(self._frames) - 1, -1, -1):
            if self._frames[index][0] == lower_tag:
                for _, mounts in self._frames[index:]:
                    for mount in mounts:
                        mount.closed = True
                del self._frames[index:]
                return

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._mark_content()

    def _mark_content(self) -> None:
        for _, mounts in self._frames:
            for mount in mounts:
                mount.has_content = True

    def _collect(self, tag: str, attrs: list[tuple[str, str | None]]) -> list[_Mount]:
        mounts: list[_Mount] = []
        for name, value in attrs:
            if not value:
                continue
            lower_name = name.lower()
            if lower_name == "data-tb-exercise":
                self.exercise_ids.append(value)
                mounts.append(_Mount(lower_name, value, tag.lower()))
            elif lower_name == "data-tb-widget":
                self.widget_ids.append(value)
                mounts.append(_Mount(lower_name, value, tag.lower()))
        self.mounts.extend(mounts)
        return mounts


def _parse_mounts(html: str) -> _MountRefParser:
    parser = _MountRefParser()
    parser.feed(html)
    parser.close()
    return parser


def _find_mount_refs(html: str) -> tuple[list[str], list[str]]:
    parser = _parse_mounts(html)
    return (
        list(dict.fromkeys(parser.exercise_ids)),
        list(dict.fromkeys(parser.widget_ids)),
    )


def _mount_issues(parser: _MountRefParser) -> list[str]:
    issues: list[str] = []
    for mount in parser.mounts:
        label = f"{mount.attribute}={mount.value}"
        if mount.tag != "div" or mount.self_closing or mount.has_content or not mount.closed:
            issues.append(f"{label} mount must be an empty <div>")
    return issues


def validate_pack(pack_dir: Path) -> ValidationReport:
    report = ValidationReport()
    if not pack_dir.is_dir():
        report.errors.append(Issue("pack.missing", f"pack directory not found: {pack_dir}"))
        return report

    if _load(pack_dir / "pack.yaml", PackMeta, report) is None:
        return report

    concepts_file = _load(pack_dir / "concepts.yaml", ConceptsFile, report)
    exercises_file = _load(pack_dir / "exercises.yaml", ExercisesFile, report)
    resources_file = _load(pack_dir / "resources.yaml", ResourcesFile, report)
    widgets_path = pack_dir / "widgets.yaml"
    widgets_file = (
        _load(widgets_path, WidgetsFile, report)
        if widgets_path.is_file()
        else WidgetsFile(schema="tb/1", widgets=[])
    )
    # A failed optional collection file is already reported as load.invalid.
    # Keep going so broken references in the remaining files are still found.
    if not concepts_file:
        return report

    concept_items = concepts_file.concepts
    exercise_items = exercises_file.exercises if exercises_file else []
    resource_items = resources_file.resources if resources_file else []
    widget_items = widgets_file.widgets if widgets_file else []

    concepts = {item.id: item for item in concept_items}
    exercises = {item.id: item for item in exercise_items}
    resources = {item.id: item for item in resource_items}
    widgets = {item.id: item for item in widget_items}

    root = pack_dir.resolve()
    for widget in widgets.values():
        template_path = (pack_dir / widget.spec.template).resolve()
        if root not in template_path.parents:
            report.errors.append(
                Issue("widget.template_path", f"template escapes pack: {widget.spec.template}")
            )
            continue
        if not template_path.is_file():
            report.errors.append(
                Issue("widget.template", f"missing widget template: {template_path}")
            )
            continue
        try:
            template_text = template_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report.errors.append(
                Issue("widget.template", f"cannot read template: {exc}", str(template_path))
            )
            continue
        for issue in find_forbidden_html(template_text):
            report.errors.append(Issue("widget.template", issue, str(template_path)))

    for label, items, source in (
        ("concept", concepts, concept_items),
        ("exercise", exercises, exercise_items),
        ("resource", resources, resource_items),
        ("widget", widgets, widget_items),
    ):
        if len(items) != len(source):
            report.errors.append(Issue(f"{label}.duplicate", f"duplicate {label} id"))

    modules: dict[str, Module] = {}
    manifests: dict[str, LessonManifest] = {}

    modules_dir = pack_dir / "modules"
    for module_path in sorted(modules_dir.glob("*/module.yaml")):
        module = _load(module_path, Module, report)
        if module is None:
            continue
        if module.id in modules:
            report.errors.append(Issue("module.duplicate", f"duplicate module {module.id}"))
        modules[module.id] = module
        for lesson_id in module.lessons:
            lesson_path = module_path.parent / "lessons" / f"{lesson_id}.html"
            try:
                manifest, body = load_lesson_file(lesson_path)
            except ContentError as exc:
                report.errors.append(Issue("lesson.load", str(exc), str(lesson_path)))
                continue
            if manifest.id != lesson_id:
                report.errors.append(
                    Issue(
                        "lesson.id",
                        f"manifest id {manifest.id} != file id {lesson_id}",
                        str(lesson_path),
                    )
                )
            if manifest.module != module.id:
                report.errors.append(
                    Issue(
                        "lesson.module",
                        f"manifest module {manifest.module} != {module.id}",
                        str(lesson_path),
                    )
                )
            if manifest.id in manifests:
                report.errors.append(Issue("lesson.duplicate", f"duplicate lesson {manifest.id}"))
            manifests[manifest.id] = manifest
            try:
                sanitize_fragment(body)
            except ValueError as exc:  # nh3 raises ValueError on bad input
                report.errors.append(
                    Issue("lesson.html", f"sanitizer failed: {exc}", str(lesson_path))
                )
            for issue in find_forbidden_html(body):
                report.errors.append(Issue("lesson.html", issue, str(lesson_path)))
            mount_parser = _parse_mounts(body)
            exercise_refs = list(dict.fromkeys(mount_parser.exercise_ids))
            widget_refs = list(dict.fromkeys(mount_parser.widget_ids))
            for message in _mount_issues(mount_parser):
                report.errors.append(Issue("mount.invalid", message, str(lesson_path)))
            for exercise_id in exercise_refs:
                if exercise_id not in exercises:
                    report.errors.append(
                        Issue(
                            "lesson.exercise_ref",
                            f"{manifest.id} mounts missing exercise {exercise_id}",
                            str(lesson_path),
                        )
                    )
            listed_exercises = list(dict.fromkeys(manifest.exercises))
            for exercise_id in exercise_refs:
                if exercise_id not in listed_exercises:
                    report.errors.append(
                        Issue(
                            "lesson.exercise_unlisted",
                            f"{manifest.id} mounts exercise {exercise_id} not listed in manifest",
                            str(lesson_path),
                        )
                    )
            for exercise_id in listed_exercises:
                if exercise_id not in exercise_refs:
                    report.errors.append(
                        Issue(
                            "lesson.exercise_unmounted",
                            f"{manifest.id} lists exercise {exercise_id} but does not mount it",
                            str(lesson_path),
                        )
                    )
            for widget_id in widget_refs:
                if widget_id not in widgets:
                    report.errors.append(
                        Issue(
                            "lesson.widget_ref",
                            f"{manifest.id} mounts missing widget {widget_id}",
                            str(lesson_path),
                        )
                    )

    if not manifests:
        report.errors.append(Issue("pack.no_lessons", "pack has no lessons", str(pack_dir)))

    graph = {cid: list(concept.prerequisites) for cid, concept in concepts.items()}
    for cycle in find_cycles(graph):
        report.errors.append(Issue("concept.cycle", f"prerequisite cycle: {' -> '.join(cycle)}"))

    def require(label: str, refs: list[str], pool: dict, owner: str) -> None:
        for ref in refs:
            if ref not in pool:
                report.errors.append(
                    Issue(f"{label}.missing", f"{owner} references missing {label} {ref}")
                )

    for concept in concepts.values():
        require("concept", concept.prerequisites, concepts, concept.id)
        require("concept", concept.related, concepts, concept.id)
        require("resource", concept.resources, resources, concept.id)
    for exercise in exercises.values():
        require("concept", exercise.concepts, concepts, exercise.id)
    for resource in resources.values():
        require("concept", resource.coverage, concepts, resource.id)
    for module in modules.values():
        require("concept", module.concepts, concepts, module.id)
        require("lesson", module.lessons, manifests, module.id)
    for manifest in manifests.values():
        require("module", [manifest.module], modules, manifest.id)
        require("concept", manifest.concepts, concepts, manifest.id)
        require("concept", manifest.prerequisites, concepts, manifest.id)
        require("exercise", manifest.exercises, exercises, manifest.id)
        require("resource", manifest.resources, resources, manifest.id)

    lesson_concepts = {cid for manifest in manifests.values() for cid in manifest.concepts}
    exercise_concepts = {cid for exercise in exercises.values() for cid in exercise.concepts}
    for cid in concepts:
        if cid not in lesson_concepts:
            report.warnings.append(Issue("concept.no_lesson", f"{cid} has no lesson", str(pack_dir)))
        if cid not in exercise_concepts:
            report.warnings.append(
                Issue("concept.no_exercise", f"{cid} has no exercise", str(pack_dir))
            )
    for manifest in manifests.values():
        if not manifest.exercises:
            report.warnings.append(Issue("lesson.no_exercise", f"{manifest.id} has no exercises"))
        if not manifest.resources:
            report.warnings.append(Issue("lesson.no_resource", f"{manifest.id} has no resources"))
    for resource in resources.values():
        if resource.trust == "D":
            report.errors.append(Issue(
                "resource.trust", f"{resource.id} trust D is not usable"
            ))
        elif resource.role == "required" and resource.trust not in {"A", "B"}:
            report.errors.append(Issue(
                "resource.required_trust",
                f"{resource.id} required resource must be trust A/B",
            ))
    for resource in resources.values():
        if not resource.last_verified:
            report.warnings.append(
                Issue("resource.no_verified", f"{resource.id} has no last_verified")
            )
        if not resource.license:
            report.warnings.append(Issue("resource.no_license", f"{resource.id} has no license"))

    return report
