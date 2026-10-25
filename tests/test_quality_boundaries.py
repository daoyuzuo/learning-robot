import ast
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
    engine = {"mastery", "schedule", "evidence", "contract", "learning"}
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if not (set(relative.parts[:-1]) & engine):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "testbridge.career" or module.startswith(
                    "testbridge.career."
                ):
                    offenders.append(str(relative))
                elif node.level >= 1 and (
                    module == "career" or module.startswith("career.")
                ):
                    offenders.append(str(relative))
                elif module == "testbridge" and any(
                    alias.name == "career" for alias in node.names
                ):
                    offenders.append(str(relative))
                elif module in ("", None) and node.level >= 1 and any(
                    alias.name == "career" for alias in node.names
                ):
                    offenders.append(str(relative))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "testbridge.career" or alias.name.startswith(
                        "testbridge.career."
                    ):
                        offenders.append(str(relative))
    assert offenders == []
