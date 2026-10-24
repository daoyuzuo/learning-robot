from pathlib import Path

import pytest

from testbridge.content.repository import (
    ContentValidationError,
    load_pack,
)

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
