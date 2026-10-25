"""Turn model output into contract files for one lesson.

Everything here treats the model output as untrusted: parse to tb/1 models,
sanitize the HTML, then write.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import yaml
from pydantic import ValidationError

from testbridge.contract.loader import load_lesson_file
from testbridge.contract.models import Exercise, Resource
from testbridge.contract.sanitize import sanitize_fragment
from testbridge.studio.outline import LEVELS, LessonPlan
from testbridge.studio.store import DraftStore

DEFAULT_MODULE_ID = "M01"
ALLOWED_TRUST = {"A", "B"}
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class LessonError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class LessonOutput:
    manifest: dict
    html: str
    exercises: list[dict] = field(default_factory=list)
    resources: list[dict] = field(default_factory=list)


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error.get("loc", ()))
    return f"{location}: {error.get('msg', 'invalid')}" if location else str(
        error.get("msg", "invalid")
    )


def _parse_exercises(items: object, concept_ids: set[str]) -> list[dict]:
    if not isinstance(items, list):
        raise LessonError("exercises 必须是数组")
    parsed: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            raise LessonError("练习缺少 id")
        exercise_id = item["id"]
        if exercise_id in seen:
            raise LessonError(f"练习 id 重复：{exercise_id}")
        try:
            exercise = Exercise.model_validate(item)
        except ValidationError as exc:
            raise LessonError(
                f"练习 {exercise_id} 不符合 tb/1：{_first_error(exc)}"
            ) from None
        for concept_id in exercise.concepts:
            if concept_id not in concept_ids:
                raise LessonError(f"练习引用了不存在的概念：{concept_id}")
        parsed.append(exercise.model_dump(exclude_none=True))
        seen.add(exercise_id)
    return parsed


def _parse_resources(items: object, concept_ids: set[str]) -> list[dict]:
    if not isinstance(items, list):
        raise LessonError("resources 必须是数组")
    parsed: list[dict] = []
    seen: set[str] = set()
    today = datetime.now(timezone.utc).date().isoformat()
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            raise LessonError("资源缺少 id")
        resource_id = item["id"]
        if resource_id in seen:
            raise LessonError(f"资源 id 重复：{resource_id}")
        if item.get("trust") not in ALLOWED_TRUST:
            raise LessonError(f"资源只有 A/B 级可用：{resource_id}")
        try:
            resource = Resource.model_validate(item)
        except ValidationError as exc:
            raise LessonError(
                f"资源 {resource_id} 不符合 tb/1：{_first_error(exc)}"
            ) from None
        for concept_id in resource.coverage:
            if concept_id not in concept_ids:
                raise LessonError(f"资源覆盖了不存在的概念：{concept_id}")
        data = resource.model_dump(exclude_none=True)
        if not data.get("last_verified"):
            data["last_verified"] = today
        parsed.append(data)
        seen.add(resource_id)
    return parsed


def parse_lesson_json(
    raw: str, lesson: LessonPlan, concept_ids: set[str]
) -> LessonOutput:
    text = _FENCE_RE.sub("", raw.strip()).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LessonError(f"写课输出不是合法 JSON：{exc.msg}") from None
    if not isinstance(data, dict):
        raise LessonError("写课输出必须是 JSON 对象")

    html = data.get("html")
    if not isinstance(html, str) or "<article" not in html:
        raise LessonError("缺少 HTML 正文")
    if re.search(r"<\s*script", html, re.IGNORECASE):
        raise LessonError("正文不得包含脚本")
    clean = sanitize_fragment(html)
    if "<article" not in clean:
        raise LessonError("正文净化后为空")

    manifest = data.get("manifest") if isinstance(data.get("manifest"), dict) else {}
    objectives = manifest.get("objectives") or lesson.objectives
    minutes = manifest.get("minutes") or lesson.minutes

    exercises = _parse_exercises(data.get("exercises") or [], concept_ids)
    resources = _parse_resources(data.get("resources") or [], concept_ids)

    return LessonOutput(
        manifest={
            "title": str(manifest.get("title") or lesson.title),
            "minutes": int(minutes),
            "objectives": [str(item) for item in objectives],
        },
        html=clean,
        exercises=exercises,
        resources=resources,
    )


def _load_list(store: DraftStore, draft_id: str, relative: str, key: str) -> list:
    try:
        data = yaml.safe_load(store.read(draft_id, relative))
    except FileNotFoundError:
        return []
    if not isinstance(data, dict):
        return []
    return list(data.get(key) or [])


def _dump(data: dict) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def _drop_old_lesson_ids(
    store: DraftStore,
    draft_id: str,
    module_id: str,
    lesson_id: str,
    existing_exercises: list,
    existing_resources: list,
) -> tuple[list, list]:
    """For a rewrite, drop IDs owned by the lesson's previous manifest.

    Only IDs recorded in the old lesson file are removed; IDs claimed by other
    lessons are untouched and still trigger the collision checks.
    """
    old_path = (
        store.path(draft_id)
        / "modules" / module_id / "lessons" / f"{lesson_id}.html"
    )
    if not old_path.is_file():
        return existing_exercises, existing_resources
    try:
        old_manifest, _ = load_lesson_file(old_path)
    except Exception:
        return existing_exercises, existing_resources
    old_exercises = set(old_manifest.exercises)
    old_resources = set(old_manifest.resources)
    return (
        [item for item in existing_exercises if item.get("id") not in old_exercises],
        [item for item in existing_resources if item.get("id") not in old_resources],
    )


def write_lesson(
    store: DraftStore,
    draft_id: str,
    lesson: LessonPlan,
    output: LessonOutput,
    *,
    replace: bool = False,
) -> None:
    module_id = lesson.module_id or DEFAULT_MODULE_ID
    existing_exercises = _load_list(store, draft_id, "exercises.yaml", "exercises")
    existing_resources = _load_list(store, draft_id, "resources.yaml", "resources")
    if replace:
        existing_exercises, existing_resources = _drop_old_lesson_ids(
            store, draft_id, module_id, lesson.lesson_id,
            existing_exercises, existing_resources,
        )

    known_exercises = {item.get("id") for item in existing_exercises}
    known_resources = {item.get("id") for item in existing_resources}

    for exercise in output.exercises:
        if exercise["id"] in known_exercises:
            raise LessonError(f"练习 id 已存在：{exercise['id']}")
    for resource in output.resources:
        if resource["id"] in known_resources:
            raise LessonError(f"资源 id 已存在：{resource['id']}")

    module = yaml.safe_load(
        store.read(draft_id, f"modules/{module_id}/module.yaml")
    )
    module_concepts = list(module.get("concepts") or [])
    used_concepts: list[str] = []
    for exercise in output.exercises:
        for concept_id in exercise.get("concepts") or []:
            if concept_id not in used_concepts:
                used_concepts.append(concept_id)
    manifest_concepts = (
        list(lesson.concepts) or used_concepts or module_concepts
    )
    level = str(store.load(draft_id).get("level") or "L2")
    target_level = level if level in LEVELS else "L2"

    manifest = {
        "schema": "tb/1",
        "id": lesson.lesson_id,
        "title": output.manifest["title"],
        "module": module_id,
        "concepts": manifest_concepts,
        "target_level": target_level,
        "minutes": output.manifest["minutes"],
        "objectives": output.manifest["objectives"],
        "prerequisites": [],
        "exercises": [item["id"] for item in output.exercises],
        "resources": [item["id"] for item in output.resources],
    }

    document = (
        '<script type="application/json" id="tb-manifest">\n'
        + json.dumps(manifest, ensure_ascii=False, indent=2)
        + "\n</script>\n"
        + output.html
    )

    store.write(
        draft_id, "exercises.yaml",
        _dump({"schema": "tb/1", "exercises": existing_exercises + output.exercises}),
    )
    store.write(
        draft_id, "resources.yaml",
        _dump({"schema": "tb/1", "resources": existing_resources + output.resources}),
    )
    store.write(
        draft_id,
        f"modules/{module_id}/lessons/{lesson.lesson_id}.html",
        document,
    )

    lessons = list(module.get("lessons") or [])
    if lesson.lesson_id not in lessons:
        lessons.append(lesson.lesson_id)
        module["lessons"] = lessons
        store.write(
            draft_id, f"modules/{module_id}/module.yaml", _dump(module)
        )
