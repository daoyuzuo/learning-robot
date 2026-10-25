"""Validation, resource verification, and promotion."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import yaml

from testbridge.contract.validator import validate_pack
from testbridge.quality.evaluate import QualityUnavailable, evaluate_draft
from testbridge.quality.report import QualityReport
from testbridge.studio.store import DraftStore

CONTENT_FILES = (
    "pack.yaml", "concepts.yaml", "exercises.yaml", "resources.yaml", "widgets.yaml",
)
CONTENT_DIRS = ("modules", "assets")


class PromoteError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ValidationSummary:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_draft(store: DraftStore, draft_id: str) -> ValidationSummary:
    report = validate_pack(store.path(draft_id))
    return ValidationSummary(
        errors=[f"{issue.code}: {issue.message}" for issue in report.errors],
        warnings=[f"{issue.code}: {issue.message}" for issue in report.warnings],
    )


def quality_draft(store: DraftStore, draft_id: str) -> QualityReport:
    draft = store.load(draft_id)
    return evaluate_draft(
        store.path(draft_id),
        research_dir=store.path(draft_id) / "research",
        budget=int(draft.get("searches_per_lesson") or 1),
    )


def verify_resources(resources, client=None) -> list[str]:
    owned = client is None
    client = client or httpx.Client(timeout=10.0, follow_redirects=True)
    errors = []
    try:
        for resource in resources:
            resource_id = resource.get("id", "?")
            url = resource.get("url", "")
            try:
                response = client.get(url)
                if response.status_code >= 400:
                    errors.append(f"{resource_id}: HTTP {response.status_code}")
            except httpx.HTTPError as exc:
                errors.append(f"{resource_id}: {type(exc).__name__}")
    finally:
        if owned:
            client.close()
    return errors


def promote(
    store: DraftStore,
    draft_id: str,
    packs_root: Path,
    *,
    force: bool = False,
    skip_verify: bool = False,
    verifier=None,
    quality_check: Callable[[DraftStore, str], QualityReport] | None = None,
) -> Path:
    source = store.path(draft_id)
    target = packs_root / draft_id
    if target.exists() and not force:
        raise PromoteError("pack_exists", f"内容包已存在：{draft_id}")

    summary = validate_draft(store, draft_id)
    if not summary.ok:
        raise PromoteError("invalid_pack", "；".join(summary.errors[:5]))

    check_quality = quality_check or quality_draft
    try:
        quality = check_quality(store, draft_id)
    except QualityUnavailable as exc:
        raise PromoteError(
            "invalid_pack", f"{len(exc.report.errors)} error(s)"
        ) from None
    if not quality.ok:
        raise PromoteError(
            "quality_gate",
            "；".join(
                f"{issue.code}: {issue.message}" for issue in quality.errors[:5]
            ),
        )

    resources_path = source / "resources.yaml"
    if not skip_verify and resources_path.is_file():
        data = yaml.safe_load(resources_path.read_text(encoding="utf-8")) or {}
        check = verifier or verify_resources
        errors = check(data.get("resources") or [])
        if errors:
            raise PromoteError("resource_unreachable", "；".join(errors[:5]))

    target.mkdir(parents=True, exist_ok=True)
    for name in CONTENT_FILES:
        item = source / name
        if item.is_file():
            shutil.copy2(item, target / name)
    for name in CONTENT_DIRS:
        item = source / name
        if item.is_dir():
            shutil.copytree(item, target / name, dirs_exist_ok=True)
    return target
