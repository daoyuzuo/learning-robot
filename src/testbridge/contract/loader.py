"""Load tb/1 YAML files and extract lesson manifests."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from .models import LessonManifest

T = TypeVar("T", bound=BaseModel)

MANIFEST_RE = re.compile(
    r'<script\b[^>]*\bid=["\']tb-manifest["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


class ContentError(Exception):
    """Raised when a content file cannot be read or validated."""


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise ContentError(f"file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContentError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContentError(f"expected a mapping in {path}")
    return data


def load_model(path: Path, model: type[T]) -> T:
    data = load_yaml(path)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ContentError(f"invalid {model.__name__} in {path}: {exc}") from exc


def extract_manifest(html: str) -> tuple[LessonManifest, str]:
    match = MANIFEST_RE.search(html)
    if not match:
        raise ContentError("missing tb-manifest script")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ContentError(f"invalid tb-manifest JSON: {exc}") from exc
    try:
        manifest = LessonManifest.model_validate(data)
    except ValidationError as exc:
        raise ContentError(f"invalid tb-manifest: {exc}") from exc
    body = html[: match.start()] + html[match.end() :]
    return manifest, body


def load_lesson_file(path: Path) -> tuple[LessonManifest, str]:
    if not path.is_file():
        raise ContentError(f"lesson file not found: {path}")
    return extract_manifest(path.read_text(encoding="utf-8"))
