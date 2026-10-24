import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from testbridge.content.repository import (
    ContentValidationError,
    Lesson,
    list_packs,
    load_pack,
)
from testbridge.contract.validator import validate_pack

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


def test_load_pack() -> None:
    pack = load_pack(FIXTURE)
    assert pack.meta.id == "fixture"
    assert pack.concept("c-one").title == "Concept One"
    assert pack.exercise("EX-ONE").type == "single_choice"
    assert pack.lesson("L-ONE").manifest.module == "M01"


def test_lessons_in_order_and_pager() -> None:
    pack = load_pack(FIXTURE)
    lessons = pack.lessons_in_order()
    assert [item.manifest.id for item in lessons] == ["L-ONE"]
    prev, nxt = pack.prev_next("L-ONE")
    assert prev is None and nxt is None


def test_invalid_pack_raises(tmp_path: Path) -> None:
    pack_dir = tmp_path / "bad"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "schema: tb/1\nid: bad\nversion: 0.1.0\ntitle: Bad\n", encoding="utf-8"
    )
    with pytest.raises(ContentValidationError):
        load_pack(pack_dir)


def test_list_packs_finds_fixture() -> None:
    infos = list_packs(FIXTURE.parent)
    matches = [info for info in infos if info.path == FIXTURE]
    assert len(matches) == 1
    assert matches[0].meta.id == "fixture"


def test_warning_only_pack_loads(tmp_path: Path) -> None:
    warn_pack = tmp_path / "warn-pack"
    shutil.copytree(FIXTURE, warn_pack)
    concepts_path = warn_pack / "concepts.yaml"
    concepts_path.write_text(
        concepts_path.read_text(encoding="utf-8")
        + "\n  - id: c-orphan\n    title: Orphan Concept\n    domain: demo\n"
        + "    target_level: L1\n",
        encoding="utf-8",
    )

    report = validate_pack(warn_pack)
    assert report.ok
    assert any(
        issue.code == "concept.no_lesson" and "c-orphan" in issue.message
        for issue in report.warnings
    )
    assert any(
        issue.code == "concept.no_exercise" and "c-orphan" in issue.message
        for issue in report.warnings
    )

    pack = load_pack(warn_pack)
    assert pack.concept("c-orphan").title == "Orphan Concept"


def test_prev_next_middle_and_unknown() -> None:
    pack = load_pack(FIXTURE)
    first = pack.lesson("L-ONE")
    lesson_two = Lesson(
        manifest=first.manifest.model_copy(update={"id": "L-TWO"}),
        body_html=first.body_html,
        path=first.path,
    )
    module_two = pack.modules["M01"].model_copy(update={"lessons": ["L-ONE", "L-TWO"]})
    pack_two = replace(
        pack,
        modules={"M01": module_two},
        lessons={"L-ONE": first, "L-TWO": lesson_two},
    )

    assert [item.manifest.id for item in pack_two.lessons_in_order()] == ["L-ONE", "L-TWO"]
    assert pack_two.prev_next("L-ONE") == (None, lesson_two)
    assert pack_two.prev_next("L-TWO") == (first, None)
    assert pack_two.prev_next("L-NOPE") == (None, None)
