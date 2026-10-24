from pathlib import Path

from testbridge.build import build_pack
from testbridge.content.repository import load_pack
from testbridge.contract.validator import validate_pack
from testbridge.lesson.renderer import render_lesson

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"


def test_sample_pack_is_valid() -> None:
    report = validate_pack(SAMPLE)
    assert report.ok, report.errors


def test_all_lessons_render() -> None:
    pack = load_pack(SAMPLE)
    assert len(pack.lessons) == 3
    for lesson in pack.lessons_in_order():
        view = render_lesson(pack, lesson.manifest.id)
        assert view.body_html
        assert "form class=\"tb-exercise\"" in view.body_html


def test_build_sample_pack(tmp_path: Path) -> None:
    paths = build_pack(SAMPLE, tmp_path)
    assert len(paths) == 3
    assert all(path.is_file() for path in paths)
