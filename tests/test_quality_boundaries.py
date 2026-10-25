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
