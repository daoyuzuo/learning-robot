import re
from pathlib import Path

from testbridge.build import build_pack
from testbridge.content.repository import load_pack
from testbridge.contract.validator import validate_pack
from testbridge.lesson.renderer import render_lesson

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"
IMG_SRC_RE = re.compile(r'<img\b[^>]*\bsrc="([^"]+)"')


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


def test_lesson_image_paths_resolve_in_source_pack() -> None:
    pack = load_pack(SAMPLE)
    root = SAMPLE.resolve()
    checked = 0
    for lesson in pack.lessons_in_order():
        view = render_lesson(pack, lesson.manifest.id)
        for src in IMG_SRC_RE.findall(view.body_html):
            target = (lesson.path.parent / src).resolve()
            assert target.is_file(), f"{lesson.manifest.id}: missing image {src}"
            assert root in target.parents, f"{lesson.manifest.id}: image escapes pack {src}"
            checked += 1
    assert checked == 2


def test_built_lesson_image_paths_resolve(tmp_path: Path) -> None:
    paths = build_pack(SAMPLE, tmp_path)
    root = (tmp_path / "sample-sensors").resolve()
    checked = 0
    for path in paths:
        html_text = path.read_text(encoding="utf-8")
        for src in IMG_SRC_RE.findall(html_text):
            target = (path.parent / src).resolve()
            assert target.is_file(), f"{path.name}: missing built image {src}"
            assert root in target.parents, f"{path.name}: image escapes built pack {src}"
            checked += 1
    assert checked == 2


def test_widget_group_transform_survives_sanitization() -> None:
    pack = load_pack(SAMPLE)
    view = render_lesson(pack, "L-SYNC-001")
    assert '<g transform="translate(' in view.body_html
