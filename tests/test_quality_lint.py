import json
import shutil
from pathlib import Path

import pytest

from testbridge.cli import main
from testbridge.content.repository import ContentValidationError, load_pack
from testbridge.quality.lint import evaluate_lint

FIXTURES = Path(__file__).parent / "fixtures"
MINIMAL = FIXTURES / "minimal-pack"
SAMPLE = Path(__file__).parents[1] / "tests" / "fixtures" / "packs" / "sample-sensors"


def _rewrite_manifest(path: Path, **updates) -> None:
    text = path.read_text(encoding="utf-8")
    start = text.index('id="tb-manifest">') + len('id="tb-manifest">')
    end = text.index("</script>", start)
    data = json.loads(text[start:end])
    data.update(updates)
    block = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(text[:start] + "\n" + block + "\n" + text[end:], encoding="utf-8")


def _copy_minimal(tmp_path: Path) -> Path:
    pack = tmp_path / "pack"
    shutil.copytree(MINIMAL, pack)
    return pack


def _codes(report) -> set[str]:
    return {issue.code for issue in report.errors}


def test_objective_map_loads(tmp_path: Path) -> None:
    pack = _copy_minimal(tmp_path)
    lesson = pack / "modules" / "M01" / "lessons" / "L-ONE.html"
    _rewrite_manifest(lesson, objective_map={"O1": ["EX-ONE"]})
    loaded = load_pack(pack)
    assert loaded.lesson("L-ONE").manifest.objective_map == {"O1": ["EX-ONE"]}


def test_objective_map_rejects_bad_key(tmp_path: Path) -> None:
    pack = _copy_minimal(tmp_path)
    lesson = pack / "modules" / "M01" / "lessons" / "L-ONE.html"
    _rewrite_manifest(lesson, objective_map={"goal": ["EX-ONE"]})
    with pytest.raises(ContentValidationError):
        load_pack(pack)


def test_objective_map_rejects_empty_value(tmp_path: Path) -> None:
    pack = _copy_minimal(tmp_path)
    lesson = pack / "modules" / "M01" / "lessons" / "L-ONE.html"
    _rewrite_manifest(lesson, objective_map={"O1": []})
    with pytest.raises(ContentValidationError):
        load_pack(pack)


def test_lint_minimal_pack_has_warnings_not_errors() -> None:
    report = evaluate_lint(load_pack(MINIMAL))
    assert report.ok
    warnings = {issue.code for issue in report.warnings}
    assert "lint.no_worked_example" in warnings
    assert "lint.objective_map_missing" in warnings


def test_lint_l3_requires_example_and_map(tmp_path: Path) -> None:
    pack = _copy_minimal(tmp_path)
    lesson = pack / "modules" / "M01" / "lessons" / "L-ONE.html"
    _rewrite_manifest(lesson, target_level="L3")
    report = evaluate_lint(load_pack(pack))
    assert {"lint.no_worked_example", "lint.objective_map_missing"} <= _codes(report)


def test_lint_objective_exercise_unknown(tmp_path: Path) -> None:
    pack = _copy_minimal(tmp_path)
    lesson = pack / "modules" / "M01" / "lessons" / "L-ONE.html"
    _rewrite_manifest(
        lesson,
        target_level="L3",
        objective_map={"O1": ["EX-NOPE"]},
    )
    report = evaluate_lint(load_pack(pack))
    assert "lint.objective_exercise_unknown" in _codes(report)


def test_lint_placeholder_and_answer_leak(tmp_path: Path) -> None:
    pack = _copy_minimal(tmp_path)
    lesson = pack / "modules" / "M01" / "lessons" / "L-ONE.html"
    text = lesson.read_text(encoding="utf-8").replace(
        "</article>", '<p>TODO</p><p>"answer":</p></article>'
    )
    lesson.write_text(text, encoding="utf-8")
    report = evaluate_lint(load_pack(pack))
    assert {"lint.placeholder", "lint.answer_leak"} <= _codes(report)


def test_lint_primary_source_missing(tmp_path: Path) -> None:
    pack = _copy_minimal(tmp_path)
    lesson = pack / "modules" / "M01" / "lessons" / "L-ONE.html"
    _rewrite_manifest(lesson, resources=[])
    report = evaluate_lint(load_pack(pack))
    assert "lint.primary_source_missing" in _codes(report)


def test_lint_quiz_option_length(tmp_path: Path) -> None:
    pack = _copy_minimal(tmp_path)
    exercises = pack / "exercises.yaml"
    exercises.write_text(
        exercises.read_text(encoding="utf-8").replace(
            "{id: b, text: B}",
            "{id: b, text: A very long distractor option}",
        ),
        encoding="utf-8",
    )
    report = evaluate_lint(load_pack(pack))
    assert "lint.quiz_option_length" in _codes(report)


def test_lint_quiz_answer_position(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(SAMPLE, pack)
    exercises = pack / "exercises.yaml"
    extra = """
  - id: EX-LINT-01
    type: single_choice
    concepts: [sensor-time-sync]
    level: L2
    prompt: lint probe one
    options:
      - {id: a, text: A}
      - {id: b, text: B}
    answer: a
  - id: EX-LINT-02
    type: single_choice
    concepts: [sensor-time-sync]
    level: L2
    prompt: lint probe two
    options:
      - {id: a, text: A}
      - {id: b, text: B}
    answer: a
  - id: EX-LINT-03
    type: single_choice
    concepts: [sensor-time-sync]
    level: L2
    prompt: lint probe three
    options:
      - {id: a, text: A}
      - {id: b, text: B}
    answer: a
"""
    exercises.write_text(
        exercises.read_text(encoding="utf-8") + extra, encoding="utf-8"
    )
    report = evaluate_lint(load_pack(pack))
    assert "lint.quiz_answer_position" in _codes(report)


def test_cli_lint_minimal_exits_0(capsys) -> None:
    assert main(["lint", str(MINIMAL)]) == 0
    out = capsys.readouterr().out
    assert "lint:" in out


def test_cli_lint_invalid_pack_exits_2(tmp_path: Path, capsys) -> None:
    assert main(["lint", str(tmp_path / "nope")]) == 2
    assert "run tb validate first" in capsys.readouterr().out


def test_cli_lint_json(capsys) -> None:
    assert main(["lint", str(MINIMAL), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
