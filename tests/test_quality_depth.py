import json
import re
import shutil
from pathlib import Path

from testbridge.cli import main
from testbridge.content.repository import load_pack
from testbridge.quality.depth import body_char_count, evaluate_depth

FIXTURES = Path(__file__).parent / "fixtures"
MINIMAL = FIXTURES / "minimal-pack"
SAMPLE = Path(__file__).parents[1] / "tests" / "fixtures" / "packs" / "sample-sensors"


def _pad_lesson(
    path: Path, *, level: str, chars: int, sections: int, table: bool
) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r'"target_level": "L[1-4]"', f'"target_level": "{level}"', text
    )
    blocks = "".join(
        f"<section><h2>Section {index}</h2><p>content</p></section>"
        for index in range(sections)
    )
    visual = "<table><tr><td>example</td></tr></table>" if table else ""
    filler = "x" * chars
    text = text.replace("</article>", f"{blocks}{visual}<p>{filler}</p></article>")
    path.write_text(text, encoding="utf-8")


def _padded_sample(tmp_path: Path, **kwargs) -> Path:
    pack = tmp_path / "pack"
    shutil.copytree(SAMPLE, pack)
    for path in (pack / "modules").glob("*/lessons/*.html"):
        _pad_lesson(path, **kwargs)
    return pack


def test_body_char_count_ignores_tags_and_whitespace() -> None:
    assert body_char_count("<h2>标题</h2>\n<p>正文</p>") == 4


def test_minimal_pack_fails_depth() -> None:
    report = evaluate_depth(load_pack(MINIMAL))
    codes = {issue.code for issue in report.errors}
    assert not report.ok
    assert "depth.lesson_too_short" in codes
    assert "depth.too_few_exercises" in codes


def test_padded_l2_pack_passes(tmp_path: Path) -> None:
    pack = _padded_sample(
        tmp_path, level="L2", chars=2100, sections=4, table=False
    )
    report = evaluate_depth(load_pack(pack))
    assert report.ok, report.errors


def test_l3_requires_visual(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(SAMPLE, pack)
    lesson_path = next((pack / "modules").glob("*/lessons/*.html"))
    _pad_lesson(lesson_path, level="L3", chars=3600, sections=6, table=False)
    report = evaluate_depth(load_pack(pack))
    codes = {issue.code for issue in report.errors}
    assert "depth.no_table_or_figure" in codes


def test_cli_depth_fails_on_minimal(capsys) -> None:
    assert main(["depth", str(MINIMAL)]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "depth.lesson_too_short" in out
    assert "1 lesson(s)" in out


def test_cli_depth_passes_on_padded_pack(tmp_path: Path, capsys) -> None:
    pack = _padded_sample(
        tmp_path, level="L2", chars=2100, sections=4, table=False
    )
    assert main(["depth", str(pack)]) == 0
    assert "0 error(s)" in capsys.readouterr().out


def test_cli_depth_invalid_pack_exits_2(tmp_path: Path, capsys) -> None:
    assert main(["depth", str(tmp_path / "nope")]) == 2
    assert "run tb validate first" in capsys.readouterr().out


def test_cli_depth_json(tmp_path: Path, capsys) -> None:
    assert main(["depth", str(MINIMAL), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["errors"]
