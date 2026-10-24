from pathlib import Path

import pytest

from testbridge.contract.loader import (
    ContentError,
    extract_manifest,
    load_lesson_file,
    load_model,
)
from testbridge.contract.models import ConceptsFile

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


def test_load_concepts_file() -> None:
    data = load_model(FIXTURE / "concepts.yaml", ConceptsFile)
    assert data.concepts[0].id == "c-one"


def test_missing_file_raises() -> None:
    with pytest.raises(ContentError):
        load_model(FIXTURE / "missing.yaml", ConceptsFile)


def test_extract_manifest_removes_script() -> None:
    html = (FIXTURE / "modules/M01/lessons/L-ONE.html").read_text(encoding="utf-8")
    manifest, body = extract_manifest(html)
    assert manifest.id == "L-ONE"
    assert "tb-manifest" not in body
    assert "Demo Lesson" in body


def test_missing_manifest_raises() -> None:
    with pytest.raises(ContentError):
        extract_manifest("<article>no manifest</article>")


def test_load_lesson_file() -> None:
    manifest, body = load_lesson_file(FIXTURE / "modules/M01/lessons/L-ONE.html")
    assert manifest.title == "Demo Lesson"
    assert "data-tb-exercise" in body


def test_invalid_utf8_yaml_raises_content_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_bytes(b"schema: tb/1\nconcepts: [\xff]")
    with pytest.raises(ContentError):
        load_model(path, ConceptsFile)


def test_invalid_utf8_lesson_raises_content_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.html"
    path.write_bytes(b"<article>\xff</article>")
    with pytest.raises(ContentError):
        load_lesson_file(path)


def test_missing_manifest_error_includes_path(tmp_path: Path) -> None:
    path = tmp_path / "no-manifest.html"
    path.write_text("<article>no manifest</article>", encoding="utf-8")
    with pytest.raises(ContentError) as excinfo:
        load_lesson_file(path)
    assert str(path) in str(excinfo.value)


def test_invalid_manifest_json_error_includes_path(tmp_path: Path) -> None:
    path = tmp_path / "bad-json.html"
    path.write_text(
        '<script type="application/json" id="tb-manifest">{oops</script>',
        encoding="utf-8",
    )
    with pytest.raises(ContentError) as excinfo:
        load_lesson_file(path)
    assert str(path) in str(excinfo.value)
