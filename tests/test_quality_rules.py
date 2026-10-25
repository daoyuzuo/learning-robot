import json
from pathlib import Path

import pytest
import yaml

from testbridge.content.repository import load_pack
from testbridge.quality.evaluate import QualityUnavailable, evaluate_draft, evaluate_pack
from testbridge.quality.provenance import (
    evaluate_provenance, load_dossiers, normalize_url,
)
from testbridge.quality.structural import evaluate_structural


def default_resource() -> dict:
    return {
        "id": "DOC-1",
        "title": "官方文档",
        "url": "https://docs.example/x",
        "type": "official-doc",
        "trust": "A",
        "license": "Apache-2.0",
        "last_verified": "2026-10-25",
        "coverage": ["c-one"],
        "why": "官方",
    }


def default_exercises() -> list[dict]:
    return [
        {
            "id": "EX-1", "type": "single_choice", "concepts": ["c-one"],
            "level": "L2", "prompt": "选一个",
            "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "answer": "a",
        },
        {
            "id": "EX-2", "type": "multi_choice", "concepts": ["c-one"],
            "level": "L2", "prompt": "多选",
            "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "answer": ["a"],
        },
        {
            "id": "EX-3", "type": "short_answer", "concepts": ["c-one"],
            "level": "L2", "prompt": "简答",
            "answer": {"accepted": ["x"], "min_hits": 1},
            "rubric": [{"dimension": "d", "weight": 1.0, "criteria": "c"}],
        },
    ]


def build_pack(root: Path, **overrides) -> Path:
    concepts = overrides.get("concepts") or [
        {"id": "c-one", "title": "概念一", "domain": "d", "target_level": "L2"}
    ]
    exercises = overrides.get("exercises") or default_exercises()
    resources = overrides.get("resources")
    if resources is None:
        resources = [default_resource()]
    lesson_exercises = overrides.get(
        "lesson_exercises", [item["id"] for item in exercises]
    )
    lesson_concepts = overrides.get("lesson_concepts")
    if lesson_concepts is None:
        lesson_concepts = sorted({
            concept_id
            for item in exercises
            if item["id"] in lesson_exercises
            for concept_id in item["concepts"]
        })
    lesson_resources = overrides.get(
        "lesson_resources", [item["id"] for item in resources]
    )
    target_level = overrides.get("target_level", "L2")
    module_concepts = overrides.get(
        "module_concepts", [item["id"] for item in concepts]
    )

    root.mkdir(parents=True, exist_ok=True)
    (root / "pack.yaml").write_text(yaml.safe_dump({
        "schema": "tb/1", "id": "q", "version": "0.1.0", "title": "Q",
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (root / "concepts.yaml").write_text(yaml.safe_dump({
        "schema": "tb/1", "concepts": concepts,
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (root / "exercises.yaml").write_text(yaml.safe_dump({
        "schema": "tb/1", "exercises": exercises,
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (root / "resources.yaml").write_text(yaml.safe_dump({
        "schema": "tb/1", "resources": resources,
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")

    module_dir = root / "modules" / "M01"
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "module.yaml").write_text(yaml.safe_dump({
        "schema": "tb/1", "id": "M01", "title": "M", "priority": "P1",
        "concepts": module_concepts, "lessons": ["L-ONE"], "order": 1,
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")

    manifest = {
        "schema": "tb/1", "id": "L-ONE", "title": "L", "module": "M01",
        "concepts": lesson_concepts or ["c-one"],
        "target_level": target_level, "minutes": 20, "objectives": ["目标"],
        "prerequisites": [], "exercises": lesson_exercises,
        "resources": lesson_resources,
    }
    mounts = "".join(
        f'<div data-tb-exercise="{exercise_id}"></div>'
        for exercise_id in lesson_exercises
    )
    lesson_html = (
        '<script type="application/json" id="tb-manifest">\n'
        + json.dumps(manifest, ensure_ascii=False)
        + "\n</script>\n"
        + f'<article class="tb-lesson"><p>正文</p>{mounts}</article>'
    )
    lesson_path = module_dir / "lessons" / "L-ONE.html"
    lesson_path.parent.mkdir(parents=True, exist_ok=True)
    lesson_path.write_text(lesson_html, encoding="utf-8")
    return root


def test_clean_pack_has_no_structural_errors(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")

    result = evaluate_structural(load_pack(pack))

    assert result.errors == []
    assert [metric.earned for metric in result.metrics] == [15, 10, 5, 10, 10, 5, 5]


def test_concept_without_exercise(tmp_path: Path) -> None:
    concepts = [
        {"id": "c-one", "title": "C1", "domain": "d", "target_level": "L2"},
        {"id": "c-two", "title": "C2", "domain": "d", "target_level": "L2"},
    ]
    pack = build_pack(tmp_path / "pack", concepts=concepts)

    result = evaluate_structural(load_pack(pack))

    assert any(
        issue.code == "quality.concept_without_exercise" and issue.concept_id == "c-two"
        for issue in result.errors
    )


def test_lesson_too_few_exercises(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack", exercises=default_exercises()[:1])

    result = evaluate_structural(load_pack(pack))

    assert any(issue.code == "quality.lesson_too_few_exercises" for issue in result.errors)


def test_exercise_concept_outside_lesson(tmp_path: Path) -> None:
    concepts = [
        {"id": "c-one", "title": "C1", "domain": "d", "target_level": "L2"},
        {"id": "c-two", "title": "C2", "domain": "d", "target_level": "L2"},
    ]
    extra = {
        "id": "EX-4", "type": "single_choice", "concepts": ["c-two"],
        "level": "L2", "prompt": "额外",
        "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        "answer": "a",
    }
    pack = build_pack(
        tmp_path / "pack",
        concepts=concepts,
        exercises=default_exercises() + [extra],
        lesson_concepts=["c-one"],
    )

    result = evaluate_structural(load_pack(pack))

    assert any(
        issue.code == "quality.exercise_concept_outside_lesson"
        and issue.lesson_id == "L-ONE"
        for issue in result.errors
    )


def test_lesson_level_short(tmp_path: Path) -> None:
    concepts = [{"id": "c-one", "title": "C1", "domain": "d", "target_level": "L1"}]
    exercises = [{**item, "level": "L1"} for item in default_exercises()]
    pack = build_pack(
        tmp_path / "pack", concepts=concepts, exercises=exercises, target_level="L2"
    )

    result = evaluate_structural(load_pack(pack))

    codes = [issue.code for issue in result.errors]
    assert "quality.lesson_level_short" in codes
    assert "quality.concept_level_short" not in codes


def test_concept_level_short(tmp_path: Path) -> None:
    concepts = [{"id": "c-one", "title": "C1", "domain": "d", "target_level": "L3"}]
    pack = build_pack(tmp_path / "pack", concepts=concepts)

    result = evaluate_structural(load_pack(pack))

    assert any(
        issue.code == "quality.concept_level_short" and issue.concept_id == "c-one"
        for issue in result.errors
    )


def test_type_variety_warning(tmp_path: Path) -> None:
    exercises = default_exercises()[:2]
    exercises[1] = {
        **exercises[1], "type": "single_choice", "answer": "a",
    }
    pack = build_pack(tmp_path / "pack", exercises=exercises)

    result = evaluate_structural(load_pack(pack))

    assert any(issue.code == "quality.type_variety_low" for issue in result.warnings)


def test_lesson_no_resource_warning(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack", resources=[], lesson_resources=[])

    result = evaluate_structural(load_pack(pack))

    assert any(issue.code == "quality.lesson_no_resource" for issue in result.warnings)


def write_research(
    root: Path, *, queries: list[str] | None = None, hits: list[dict] | None = None
) -> Path:
    research = root / "research"
    research.mkdir(parents=True, exist_ok=True)
    payload = {
        "lesson_id": "L-ONE",
        "queries": ["q", "q2"] if queries is None else queries,
        "hits": (
            [{"url": "https://docs.example/x", "trust": "A"}]
            if hits is None else hits
        ),
    }
    (research / "L-ONE.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return research


def test_normalize_url() -> None:
    assert normalize_url("HTTPS://Docs.Example:443/X/?utm=1#top") == (
        "https://docs.example/X"
    )
    assert normalize_url("http://example.com:80") == "http://example.com/"
    assert normalize_url("ftp://example.com") == ""
    assert normalize_url("not a url") == ""


def test_traceable_resource_has_no_error(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")
    research = write_research(tmp_path / "pack")

    result = evaluate_provenance(load_pack(pack), research, budget=2)

    assert not any(
        issue.code == "quality.resource_unsourced" for issue in result.errors
    )
    assert any(
        metric.key == "provenance.traceable" and metric.earned == 15
        for metric in result.metrics
    )


def test_untraceable_resource_is_error(tmp_path: Path) -> None:
    resource = {**default_resource(), "url": "https://docs.example/other"}
    pack = build_pack(tmp_path / "pack", resources=[resource])
    research = write_research(tmp_path / "pack")

    result = evaluate_provenance(load_pack(pack), research, budget=2)

    assert any(
        issue.code == "quality.resource_unsourced"
        and issue.resource_id == "DOC-1"
        for issue in result.errors
    )


def test_missing_dossier_is_error(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")
    research = tmp_path / "pack" / "research"
    research.mkdir(parents=True)

    result = evaluate_provenance(load_pack(pack), research, budget=2)

    assert any(
        issue.code == "quality.research_missing" and issue.lesson_id == "L-ONE"
        for issue in result.errors
    )


def test_empty_dossier_is_error(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")
    research = write_research(tmp_path / "pack", hits=[])

    result = evaluate_provenance(load_pack(pack), research, budget=2)

    assert any(issue.code == "quality.research_empty" for issue in result.errors)


def test_malformed_dossier_is_error_without_missing(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")
    research = tmp_path / "pack" / "research"
    research.mkdir(parents=True)
    (research / "L-ONE.json").write_text("{bad", encoding="utf-8")

    result = evaluate_provenance(load_pack(pack), research, budget=2)

    codes = [issue.code for issue in result.errors]
    assert "quality.research_malformed" in codes
    assert "quality.research_missing" not in codes


def test_low_query_count_is_warning(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")
    research = write_research(tmp_path / "pack", queries=["q"])

    result = evaluate_provenance(load_pack(pack), research, budget=10)

    assert any(issue.code == "quality.research_queries_low" for issue in result.warnings)
    assert any(
        metric.key == "research.queries" and metric.earned == 0
        for metric in result.metrics
    )


def test_no_ab_source_is_warning(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")
    research = write_research(
        tmp_path / "pack", hits=[{"url": "https://docs.example/x", "trust": "C"}]
    )

    result = evaluate_provenance(load_pack(pack), research, budget=2)

    assert any(issue.code == "quality.lesson_no_ab_source" for issue in result.warnings)


def test_resource_trust_error(tmp_path: Path) -> None:
    resource = {**default_resource(), "trust": "C"}
    pack = build_pack(tmp_path / "pack", resources=[resource])

    result = evaluate_provenance(load_pack(pack))

    assert any(
        issue.code == "quality.resource_trust" and issue.resource_id == "DOC-1"
        for issue in result.errors
    )


def test_resource_metadata_warning(tmp_path: Path) -> None:
    resource = {**default_resource(), "license": "", "last_verified": "", "why": ""}
    pack = build_pack(tmp_path / "pack", resources=[resource])

    result = evaluate_provenance(load_pack(pack))

    assert any(
        issue.code == "quality.resource_metadata" and issue.resource_id == "DOC-1"
        for issue in result.warnings
    )


def test_no_research_omits_resource_metrics(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")

    result = evaluate_provenance(load_pack(pack), include_metrics=False)

    assert result.metrics == []


def test_load_dossiers_reports_malformed(tmp_path: Path) -> None:
    research = tmp_path / "research"
    research.mkdir()
    (research / "L-ONE.json").write_text("{bad", encoding="utf-8")

    dossiers, malformed, issues = load_dossiers(research)

    assert dossiers == {}
    assert malformed == {"L-ONE"}
    assert issues[0].code == "quality.research_malformed"


def test_clean_pack_scores_100_with_research(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")
    research = write_research(tmp_path / "pack")

    report = evaluate_pack(pack, research_dir=research, budget=2)

    assert report.ok is True
    assert report.score == 100
    assert report.possible == 100
    assert report.provenance_evaluated is True


def test_structural_only_report_is_normalized(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")

    report = evaluate_pack(pack)

    assert report.score == 100
    assert report.earned == 60
    assert report.possible == 60
    assert report.provenance_evaluated is False
    assert all(
        not metric.key.startswith("provenance.") for metric in report.metrics
    )


def test_research_without_budget_omits_query_metric(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")
    research = write_research(tmp_path / "pack")

    report = evaluate_pack(pack, research_dir=research)

    assert report.possible == 95
    assert report.score == 100
    assert all(metric.key != "research.queries" for metric in report.metrics)


def test_invalid_pack_raises_quality_unavailable(tmp_path: Path) -> None:
    with pytest.raises(QualityUnavailable):
        evaluate_pack(tmp_path / "missing")


def test_evaluate_draft_matches_evaluate_pack(tmp_path: Path) -> None:
    pack = build_pack(tmp_path / "pack")
    research = write_research(tmp_path / "pack")

    direct = evaluate_pack(pack, research_dir=research, budget=2)
    draft = evaluate_draft(pack, research_dir=research, budget=2)

    assert draft.as_dict() == direct.as_dict()


def test_warning_only_report_is_ok(tmp_path: Path) -> None:
    resource = {**default_resource(), "license": "", "why": ""}
    pack = build_pack(tmp_path / "pack", resources=[resource])
    research = write_research(tmp_path / "pack")

    report = evaluate_pack(pack, research_dir=research, budget=2)

    assert report.ok is True
    assert report.warnings
