import shutil
from pathlib import Path

from testbridge.contract.validator import validate_pack

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


def _lesson_pack(tmp_path: Path, exercise_markup: str, widget_markup: str) -> Path:
    pack = tmp_path / "pack"
    shutil.copytree(FIXTURE, pack)
    lesson = pack / "modules" / "M01" / "lessons" / "L-ONE.html"
    text = lesson.read_text(encoding="utf-8")
    text = text.replace('<div data-tb-exercise="EX-ONE"></div>', exercise_markup)
    text = text.replace('<div data-tb-widget="W-ONE"></div>', widget_markup)
    lesson.write_text(text, encoding="utf-8")
    return pack


def test_fixture_pack_is_valid() -> None:
    report = validate_pack(FIXTURE)
    assert report.ok, report.errors


def test_missing_reference_is_an_error(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "pack.yaml").write_text(
        "schema: tb/1\nid: p\nversion: 0.1.0\ntitle: P\n", encoding="utf-8"
    )
    (pack / "concepts.yaml").write_text(
        "schema: tb/1\nconcepts:\n"
        "  - {id: c-one, title: One, domain: demo, target_level: L2, prerequisites: [missing]}\n",
        encoding="utf-8",
    )
    (pack / "exercises.yaml").write_text("schema: tb/1\nexercises: []\n", encoding="utf-8")
    report = validate_pack(pack)
    assert not report.ok
    assert any("missing" in issue.message for issue in report.errors)


def test_cycle_is_an_error(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "pack.yaml").write_text(
        "schema: tb/1\nid: p\nversion: 0.1.0\ntitle: P\n", encoding="utf-8"
    )
    (pack / "concepts.yaml").write_text(
        "schema: tb/1\nconcepts:\n"
        "  - {id: c-a, title: A, domain: demo, target_level: L2, prerequisites: [c-b]}\n"
        "  - {id: c-b, title: B, domain: demo, target_level: L2, prerequisites: [c-a]}\n",
        encoding="utf-8",
    )
    report = validate_pack(pack)
    assert not report.ok
    assert any(issue.code == "concept.cycle" for issue in report.errors)


def test_unsafe_lesson_html_is_an_error(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(FIXTURE, pack)
    lesson = pack / "modules" / "M01" / "lessons" / "L-ONE.html"
    lesson.write_text(
        lesson.read_text(encoding="utf-8").replace(
            "<p>This is a demo.</p>", '<p>This is a demo.</p><script>alert(1)</script>'
        ),
        encoding="utf-8",
    )
    report = validate_pack(pack)
    assert not report.ok
    assert any(issue.code == "lesson.html" for issue in report.errors)


def test_quality_gaps_are_warnings_not_errors(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(FIXTURE, pack)
    (pack / "resources.yaml").write_text(
        "schema: tb/1\nresources:\n"
        "  - {id: DOC-ONE, title: Example, url: 'https://example.com',"
        " type: official-doc, trust: A, coverage: [c-one]}\n",
        encoding="utf-8",
    )
    report = validate_pack(pack)
    assert report.ok, report.errors
    codes = {issue.code for issue in report.warnings}
    assert {"resource.no_verified", "resource.no_license"} <= codes


def test_non_utf8_widget_template_is_an_error(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(FIXTURE, pack)
    (pack / "assets" / "widgets" / "demo.svg").write_bytes(b"\xff\xfe<svg/>")
    report = validate_pack(pack)
    assert not report.ok
    assert any(
        issue.code == "widget.template" and "cannot read template" in issue.message
        for issue in report.errors
    )


def test_single_quoted_exercise_mount_is_checked(tmp_path: Path) -> None:
    pack = _lesson_pack(
        tmp_path,
        "<div data-tb-exercise='EX-NOPE'></div>",
        '<div data-tb-widget="W-ONE"></div>',
    )
    report = validate_pack(pack)
    assert not report.ok
    assert any(
        issue.code == "lesson.exercise_ref" and "EX-NOPE" in issue.message
        for issue in report.errors
    )


def test_single_quoted_widget_mount_is_checked(tmp_path: Path) -> None:
    pack = _lesson_pack(
        tmp_path,
        '<div data-tb-exercise="EX-ONE"></div>',
        "<div data-tb-widget='W-NOPE'></div>",
    )
    report = validate_pack(pack)
    assert not report.ok
    assert any(
        issue.code == "lesson.widget_ref" and "W-NOPE" in issue.message
        for issue in report.errors
    )


def test_mount_refs_in_text_and_comments_are_ignored(tmp_path: Path) -> None:
    markup = (
        '<div data-tb-exercise="EX-ONE"></div>'
        '<code>data-tb-exercise="EX-NOPE"</code>'
        '<!-- <div data-tb-exercise="EX-NOPE"></div> -->'
    )
    pack = _lesson_pack(tmp_path, markup, '<div data-tb-widget="W-ONE"></div>')
    report = validate_pack(pack)
    assert report.ok, report.errors


def test_mount_with_fallback_content_is_invalid(tmp_path: Path) -> None:
    pack = _lesson_pack(
        tmp_path,
        '<div data-tb-exercise="EX-ONE">fallback</div>',
        '<div data-tb-widget="W-ONE"></div>',
    )
    report = validate_pack(pack)
    assert not report.ok
    assert any(
        issue.code == "mount.invalid" and "EX-ONE" in issue.message
        for issue in report.errors
    )


def test_mount_must_be_a_div(tmp_path: Path) -> None:
    pack = _lesson_pack(
        tmp_path,
        '<section data-tb-exercise="EX-ONE"></section>',
        '<div data-tb-widget="W-ONE"></div>',
    )
    report = validate_pack(pack)
    assert not report.ok
    assert any(
        issue.code == "mount.invalid" and "EX-ONE" in issue.message
        for issue in report.errors
    )


def test_whitespace_only_empty_div_mount_is_valid(tmp_path: Path) -> None:
    pack = _lesson_pack(
        tmp_path,
        '<div data-tb-exercise="EX-ONE">\n  </div>',
        '<div data-tb-widget="W-ONE">  </div>',
    )
    report = validate_pack(pack)
    assert not any(issue.code == "mount.invalid" for issue in report.errors)


def _add_exercise(pack: Path, exercise_id: str) -> None:
    exercises = pack / "exercises.yaml"
    exercises.write_text(
        exercises.read_text(encoding="utf-8")
        + f"  - id: {exercise_id}\n"
        "    type: single_choice\n"
        "    concepts: [c-one]\n"
        "    level: L1\n"
        "    prompt: Pick A.\n"
        "    options:\n"
        "      - {id: a, text: A}\n"
        "      - {id: b, text: B}\n"
        "    answer: a\n",
        encoding="utf-8",
    )


def test_mount_not_listed_in_manifest_is_an_error(tmp_path: Path) -> None:
    pack = _lesson_pack(
        tmp_path,
        '<div data-tb-exercise="EX-TWO"></div>',
        '<div data-tb-widget="W-ONE"></div>',
    )
    _add_exercise(pack, "EX-TWO")

    report = validate_pack(pack)

    assert not report.ok
    unlisted = [issue for issue in report.errors if issue.code == "lesson.exercise_unlisted"]
    assert len(unlisted) == 1
    assert "L-ONE" in unlisted[0].message
    assert "EX-TWO" in unlisted[0].message
    assert unlisted[0].path.endswith("L-ONE.html")


def test_manifest_exercise_without_mount_is_an_error(tmp_path: Path) -> None:
    pack = _lesson_pack(
        tmp_path,
        '<div data-tb-exercise="EX-ONE"></div>',
        '<div data-tb-widget="W-ONE"></div>',
    )
    _add_exercise(pack, "EX-TWO")
    lesson = pack / "modules" / "M01" / "lessons" / "L-ONE.html"
    text = lesson.read_text(encoding="utf-8")
    lesson.write_text(
        text.replace('"exercises": ["EX-ONE"]', '"exercises": ["EX-ONE", "EX-TWO"]'),
        encoding="utf-8",
    )

    report = validate_pack(pack)

    assert not report.ok
    unmounted = [issue for issue in report.errors if issue.code == "lesson.exercise_unmounted"]
    assert len(unmounted) == 1
    assert "L-ONE" in unmounted[0].message
    assert "EX-TWO" in unmounted[0].message
    assert unmounted[0].path.endswith("L-ONE.html")


def test_duplicate_widget_id_is_an_error(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(FIXTURE, pack)
    widgets = pack / "widgets.yaml"
    widgets.write_text(
        widgets.read_text(encoding="utf-8")
        + "  - id: W-ONE\n"
        "    type: parameter-svg\n"
        "    title: Duplicate\n"
        "    spec:\n"
        "      template: assets/widgets/demo.svg\n"
        "      parameters:\n"
        "        - {id: offset, label: Offset, min: -10, max: 10, default: 0}\n",
        encoding="utf-8",
    )
    report = validate_pack(pack)
    assert not report.ok
    assert any(issue.code == "widget.duplicate" for issue in report.errors)
