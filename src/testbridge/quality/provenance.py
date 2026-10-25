"""Source provenance rules: URL traceability and research dossiers."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from testbridge.content.repository import ContentPack
from testbridge.quality.report import QualityIssue, QualityMetric, proportional

AB_TRUST = {"A", "B"}


@dataclass(frozen=True)
class Dossier:
    lesson_id: str
    queries: int
    hits: list[dict]


@dataclass
class ProvenanceResult:
    metrics: list[QualityMetric] = field(default_factory=list)
    errors: list[QualityIssue] = field(default_factory=list)
    warnings: list[QualityIssue] = field(default_factory=list)


def _error(code: str, message: str, **kwargs) -> QualityIssue:
    return QualityIssue(code=code, message=message, severity="error", **kwargs)


def _warning(code: str, message: str, **kwargs) -> QualityIssue:
    return QualityIssue(code=code, message=message, severity="warning", **kwargs)


def normalize_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return ""
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        return ""
    host = (parts.hostname or "").lower()
    if not host:
        return ""
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    path = parts.path.rstrip("/") or "/"
    return f"{scheme}://{host}{path}"


def _is_ab(hit: dict) -> bool:
    trust = hit.get("trust")
    if isinstance(trust, str):
        return trust in AB_TRUST
    try:
        return int(hit.get("authority")) >= 2
    except (TypeError, ValueError):
        return False


def load_dossiers(
    research_dir: Path,
) -> tuple[dict[str, Dossier], set[str], list[QualityIssue]]:
    dossiers: dict[str, Dossier] = {}
    malformed: set[str] = set()
    issues: list[QualityIssue] = []
    if not research_dir.is_dir():
        return dossiers, malformed, issues
    for path in sorted(research_dir.glob("*.json")):
        lesson_id = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if not isinstance(data, dict) or not isinstance(data.get("hits"), list):
            malformed.add(lesson_id)
            issues.append(_error(
                "quality.research_malformed",
                f"{lesson_id} 调研档案无法解析",
                lesson_id=lesson_id,
            ))
            continue
        hits = [hit for hit in data["hits"] if isinstance(hit, dict)]
        queries = data.get("queries")
        dossiers[lesson_id] = Dossier(
            lesson_id=lesson_id,
            queries=len(queries) if isinstance(queries, list) else 0,
            hits=hits,
        )
    return dossiers, malformed, issues


def evaluate_provenance(
    pack: ContentPack,
    research_dir: Path | None = None,
    budget: int | None = None,
    *,
    include_metrics: bool = True,
) -> ProvenanceResult:
    result = ProvenanceResult()
    resources = list(pack.resources.values())

    trust_ok = sum(1 for resource in resources if resource.trust in AB_TRUST)
    metadata_ok = sum(
        1
        for resource in resources
        if resource.license and resource.last_verified and resource.why
    )
    for resource in resources:
        if resource.trust not in AB_TRUST:
            result.errors.append(_error(
                "quality.resource_trust",
                f"资源 {resource.id} 的 trust 是 {resource.trust}，只允许 A/B",
                resource_id=resource.id,
            ))
        if not (resource.license and resource.last_verified and resource.why):
            result.warnings.append(_warning(
                "quality.resource_metadata",
                f"资源 {resource.id} 缺少 license / last_verified / why",
                resource_id=resource.id,
            ))
    if include_metrics:
        result.metrics.append(QualityMetric(
            "provenance.trust", "资源可信",
            proportional(trust_ok, len(resources), 10), 10,
            f"{trust_ok}/{len(resources)}",
        ))
        result.metrics.append(QualityMetric(
            "provenance.metadata", "资源元数据完整",
            proportional(metadata_ok, len(resources), 5), 5,
            f"{metadata_ok}/{len(resources)}",
        ))

    if research_dir is None:
        return result

    dossiers, malformed, issues = load_dossiers(research_dir)
    result.errors.extend(issues)

    all_urls = {
        normalize_url(str(hit.get("url") or ""))
        for dossier in dossiers.values()
        for hit in dossier.hits
    }
    ab_urls = {
        normalize_url(str(hit.get("url") or ""))
        for dossier in dossiers.values()
        for hit in dossier.hits
        if _is_ab(hit)
    }
    all_urls.discard("")
    ab_urls.discard("")
    traceable = 0
    for resource in resources:
        normalized = normalize_url(resource.url)
        if normalized and normalized in ab_urls:
            traceable += 1
        elif normalized and normalized in all_urls:
            result.errors.append(_error(
                "quality.resource_untrusted_source",
                f"资源 {resource.id} 的来源命中不是 A/B",
                resource_id=resource.id,
            ))
        else:
            result.errors.append(_error(
                "quality.resource_unsourced",
                f"资源 {resource.id} 的 URL 不在任何调研档案中",
                resource_id=resource.id,
            ))
    result.metrics.append(QualityMetric(
        "provenance.traceable", "资源可追溯",
        proportional(traceable, len(resources), 15), 15,
        f"{traceable}/{len(resources)}",
    ))

    lessons = pack.lessons_in_order()
    dossier_ok = 0
    query_ok = 0
    for lesson in lessons:
        lesson_id = lesson.manifest.id
        dossier = dossiers.get(lesson_id)
        if dossier is None:
            if lesson_id not in malformed:
                result.errors.append(_error(
                    "quality.research_missing",
                    f"{lesson_id} 没有调研档案",
                    lesson_id=lesson_id,
                ))
            continue
        if not dossier.hits:
            result.errors.append(_error(
                "quality.research_empty",
                f"{lesson_id} 的调研档案没有命中",
                lesson_id=lesson_id,
            ))
            continue
        dossier_ok += 1
        if not any(_is_ab(hit) for hit in dossier.hits):
            result.warnings.append(_warning(
                "quality.lesson_no_ab_source",
                f"{lesson_id} 没有 A/B 级来源",
                lesson_id=lesson_id,
            ))
        if budget is not None:
            threshold = math.ceil(budget / 2)
            if dossier.queries < threshold:
                result.warnings.append(_warning(
                    "quality.research_queries_low",
                    f"{lesson_id} 只查询了 {dossier.queries} 次，低于 {threshold}",
                    lesson_id=lesson_id,
                ))
            else:
                query_ok += 1

    result.metrics.append(QualityMetric(
        "research.dossiers", "调研可用",
        proportional(dossier_ok, len(lessons), 5), 5,
        f"{dossier_ok}/{len(lessons)}",
    ))
    if budget is not None:
        result.metrics.append(QualityMetric(
            "research.queries", "调研充分",
            proportional(query_ok, len(lessons), 5), 5,
            f"{query_ok}/{len(lessons)}",
        ))
    return result
