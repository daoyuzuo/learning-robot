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
