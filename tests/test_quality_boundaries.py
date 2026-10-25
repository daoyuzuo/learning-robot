import re
from pathlib import Path


def test_quality_package_has_no_forbidden_imports() -> None:
    root = Path(__file__).parents[1] / "src" / "testbridge" / "quality"
    pattern = re.compile(
        r"testbridge\.(studio|learning|mastery|schedule|evidence)"
    )
    offenders = [
        path.name
        for path in sorted(root.glob("*.py"))
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_engine_does_not_import_career() -> None:
    root = Path(__file__).parents[1] / "src" / "testbridge"
    pattern = re.compile(r"testbridge\.career")
    offenders = [
        str(path.relative_to(root))
        for path in sorted(root.rglob("*.py"))
        if path.parts[-2] in {
            "mastery", "schedule", "evidence", "contract", "learning"
        }
        and pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
