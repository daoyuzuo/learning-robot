import shutil
from pathlib import Path

from testbridge.contract.validator import validate_pack

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


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
