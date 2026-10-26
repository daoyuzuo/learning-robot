import json
from pathlib import Path

import pytest

from testbridge.content.repository import load_pack
from testbridge.quality.evaluate import _prompt_versions, evaluate_pack
from testbridge.quality.figures import evaluate_figures

FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "minimal-pack"


def copy_pack(tmp_path: Path, body: str | None = None) -> Path:
    import shutil

    root = tmp_path / "pack"
    shutil.copytree(FIXTURE, root)
    if body is not None:
        lesson = root / "modules" / "M01" / "lessons" / "L-ONE.html"
        text = lesson.read_text(encoding="utf-8")
        head, _, _ = text.partition("<article")
        # Keep the exercise mount: the pack must stay contract-valid.
        body = body.replace(
            "</article>", '<div data-tb-exercise="EX-ONE"></div></article>'
        )
        lesson.write_text(head + body, encoding="utf-8")
    return root


def write_draft(root: Path, version: str) -> None:
    (root / "draft.json").write_text(json.dumps({
        "steps": {"lessons": {"L-ONE": {"prompt_version": version}}},
    }), encoding="utf-8")


def test_unresolved_mount_is_an_error(tmp_path: Path) -> None:
    root = copy_pack(
        tmp_path,
        '<article class="tb-lesson"><div data-tb-figure="FIG-1"></div></article>',
    )
    result = evaluate_figures(load_pack(root), {})
    assert any(
        issue.code == "quality.figure_mount_unresolved" for issue in result.errors
    )


def test_quoted_mount_syntax_is_not_an_error(tmp_path: Path) -> None:
    root = copy_pack(
        tmp_path,
        '<article class="tb-lesson">'
        '<p>正文要写 <code>data-tb-figure="FIG-1"</code> 这样的属性。</p>'
        '<pre><code>&lt;div data-tb-figure="FIG-1"&gt;&lt;/div&gt;</code></pre>'
        "</article>",
    )
    result = evaluate_figures(load_pack(root), {})
    assert result.errors == []


def test_non_div_attribute_is_not_a_mount(tmp_path: Path) -> None:
    root = copy_pack(
        tmp_path,
        '<article class="tb-lesson">'
        '<span data-tb-figure="FIG-1"></span></article>',
    )
    result = evaluate_figures(load_pack(root), {})
    assert result.errors == []


def test_uppercase_figure_tag_satisfies_coverage(tmp_path: Path) -> None:
    root = copy_pack(
        tmp_path,
        '<article class="tb-lesson"><FIGURE class="tb-figure">'
        "<svg></svg><figcaption>x</figcaption></FIGURE></article>",
    )
    result = evaluate_figures(load_pack(root), {"L-ONE": "studio/4"})
    assert result.warnings == []


def test_new_prompt_without_figure_warns(tmp_path: Path) -> None:
    root = copy_pack(
        tmp_path, '<article class="tb-lesson"><p>正文</p></article>'
    )
    result = evaluate_figures(load_pack(root), {"L-ONE": "studio/4"})
    assert any(issue.code == "quality.lesson_no_figure" for issue in result.warnings)


def test_old_prompt_version_is_skipped(tmp_path: Path) -> None:
    root = copy_pack(
        tmp_path, '<article class="tb-lesson"><p>正文</p></article>'
    )
    result = evaluate_figures(load_pack(root), {"L-ONE": "studio/3"})
    assert not any(issue.code == "quality.lesson_no_figure" for issue in result.warnings)


def test_figure_present_is_clean(tmp_path: Path) -> None:
    root = copy_pack(
        tmp_path,
        '<article class="tb-lesson"><figure class="tb-figure">'
        "<svg></svg><figcaption>x</figcaption></figure></article>",
    )
    result = evaluate_figures(load_pack(root), {"L-ONE": "studio/4"})
    assert result.errors == []
    assert result.warnings == []


def test_evaluate_pack_reads_prompt_versions_from_draft_json(tmp_path: Path) -> None:
    root = copy_pack(tmp_path)
    write_draft(root, "studio/4")

    report = evaluate_pack(root)

    assert any(issue.code == "quality.lesson_no_figure" for issue in report.warnings)


def test_published_pack_has_no_figure_warnings(tmp_path: Path) -> None:
    root = copy_pack(tmp_path)

    report = evaluate_pack(root)

    assert not any(issue.code == "quality.lesson_no_figure" for issue in report.warnings)


@pytest.mark.parametrize("payload", [
    "{not json",
    json.dumps({"steps": ["lessons"]}),
    json.dumps({"steps": {"lessons": {"L-ONE": "studio/4"}}}),
    json.dumps(["not", "an", "object"]),
])
def test_malformed_draft_json_yields_no_prompt_versions(
    tmp_path: Path, payload: str
) -> None:
    root = copy_pack(tmp_path)
    (root / "draft.json").write_text(payload, encoding="utf-8")

    assert _prompt_versions(root) == {}
    report = evaluate_pack(root)
    assert not any(
        issue.code == "quality.lesson_no_figure" for issue in report.warnings
    )
