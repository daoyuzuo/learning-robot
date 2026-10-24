"""Load tb/1 YAML files and extract lesson manifests."""

from __future__ import annotations

import datetime as dt
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


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContentError(f"cannot read {path}: {exc}") from exc


def _normalize_yaml_scalars(value):
    """Turn YAML implicit date/datetime scalars into ISO strings.

    ``tb/1`` stores dates as strings, but ``yaml.safe_load`` parses an unquoted
    ISO date into ``datetime.date``. Normalize at the loader boundary so authors
    can write ``created: 2026-10-24`` as documented in the contract.
    """
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize_yaml_scalars(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_yaml_scalars(item) for item in value]
    return value


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(_read_text(path))
    except yaml.YAMLError as exc:
        raise ContentError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContentError(f"expected a mapping in {path}")
    return _normalize_yaml_scalars(data)


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
    html = _read_text(path)
    try:
        return extract_manifest(html)
    except ContentError as exc:
        raise ContentError(f"{path}: {exc}") from exc
