"""The scaffold command produces a valid tb/1 skeleton without generation."""

from __future__ import annotations

from pathlib import Path

from testbridge.cli import main
from testbridge.contract.validator import validate_pack


def test_scaffold_creates_a_valid_pack(tmp_path: Path) -> None:
    target = tmp_path / "demo"

    assert main([
        "scaffold", "demo", "--dir", str(tmp_path), "--title", "示例课程",
    ]) == 0

    assert target.is_dir()
    assert (target / "pack.yaml").is_file()
    assert (target / "concepts.yaml").is_file()
    assert (target / "exercises.yaml").is_file()
    assert (target / "resources.yaml").is_file()
    assert (target / "modules/M01/module.yaml").is_file()
    lesson = target / "modules/M01/lessons/L-001-001.html"
    assert lesson.is_file()
    assert 'data-tb-exercise="EX-1"' in lesson.read_text(encoding="utf-8")
    assert 'data-tb-exercise="EX-2"' in lesson.read_text(encoding="utf-8")

    report = validate_pack(target)
    assert report.ok, [f"{i.code}: {i.message}" for i in report.errors]


def test_scaffold_refuses_existing_or_invalid_ids(tmp_path: Path) -> None:
    assert main([
        "scaffold", "demo", "--dir", str(tmp_path),
    ]) == 0
    assert main([
        "scaffold", "demo", "--dir", str(tmp_path),
    ]) == 2
    assert main([
        "scaffold", "../evil", "--dir", str(tmp_path),
    ]) == 2
    assert not (tmp_path.parent / "evil").exists()


def test_scaffold_rejects_invalid_level(tmp_path: Path) -> None:
    assert main([
        "scaffold", "demo", "--dir", str(tmp_path), "--level", "L9",
    ]) == 2
    assert not (tmp_path / "demo").exists()
