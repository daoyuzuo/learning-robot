import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from testbridge.build import STANDALONE_CORE_JS, build_pack

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"
NODE = shutil.which("node")


def test_build_creates_standalone(tmp_path: Path) -> None:
    paths = build_pack(FIXTURE, tmp_path)
    assert len(paths) == 1
    html = paths[0].read_text(encoding="utf-8")
    assert "Demo Lesson" in html
    assert "TB_EXERCISES" in html
    assert "localStorage" in html
    assert "tb-exercise" in html
    # The lesson body already starts with <article class="tb-lesson">; the
    # standalone template must not wrap it a second time.
    assert html.count('<article class="tb-lesson">') == 1
    assert '<main class="tb-main tb-lesson-main">' in html
    assert (tmp_path / "fixture" / "assets" / "widgets" / "demo.svg").is_file()


def test_standalone_js_falls_back_to_memory_when_storage_fails(tmp_path: Path) -> None:
    paths = build_pack(FIXTURE, tmp_path)
    html_text = paths[0].read_text(encoding="utf-8")

    assert "let memory = null;" in html_text
    assert "未检测到本地存储，证据仅保留在本次会话，请立即导出。" in html_text
    assert "memory.slice()" in html_text
    assert re.search(
        r"try\s*\{\s*localStorage\.setItem\(KEY, JSON\.stringify\(rows\)\);\s*memory = null;\s*\}\s*catch",
        html_text,
    )
    assert "memory = rows.slice();" in html_text


def _two_lesson_pack(tmp_path: Path) -> Path:
    pack = tmp_path / "two-lesson-pack"
    shutil.copytree(FIXTURE, pack)
    module_file = pack / "modules" / "M01" / "module.yaml"
    module_file.write_text(
        module_file.read_text(encoding="utf-8").replace(
            "lessons: [L-ONE]", "lessons: [L-ONE, L-TWO]"
        ),
        encoding="utf-8",
    )
    (pack / "modules" / "M01" / "lessons" / "L-TWO.html").write_text(
        """<script type="application/json" id="tb-manifest">
{
  "schema": "tb/1",
  "id": "L-TWO",
  "title": "Second Lesson",
  "module": "M01",
  "concepts": ["c-one"],
  "target_level": "L2",
  "minutes": 10,
  "objectives": ["Explain two"],
  "prerequisites": [],
  "exercises": ["EX-ONE"],
  "resources": ["DOC-ONE"]
}
</script>
<article class="tb-lesson">
  <h1>Second Lesson</h1>
  <div data-tb-exercise="EX-ONE"></div>
</article>
""",
        encoding="utf-8",
    )
    return pack


def test_build_filters_to_single_lesson(tmp_path: Path) -> None:
    pack = _two_lesson_pack(tmp_path)

    paths = build_pack(pack, tmp_path / "dist", lesson_id="L-ONE")

    assert len(paths) == 1
    assert paths[0].name == "L-ONE.html"
    target = tmp_path / "dist" / "fixture"
    assert not (target / "modules" / "M01" / "lessons" / "L-TWO.html").exists()
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["lessons"] == ["L-ONE"]


def _run_core_js(tmp_path: Path, body: str):
    if NODE is None:
        pytest.skip("Node.js is required to exercise standalone JS")
    script = tmp_path / "core.js"
    script.write_text(STANDALONE_CORE_JS + "\n" + body, encoding="utf-8")
    result = subprocess.run(
        [NODE, str(script)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.stderr == ""
    return json.loads(result.stdout)


def test_standalone_multi_choice_uses_jaccard_score(tmp_path: Path) -> None:
    results = _run_core_js(
        tmp_path,
        """
const ex = { type: "multi_choice", answer: ["a", "b"] };
console.log(JSON.stringify([
  grade(ex, ["a", "b"]),
  grade(ex, ["a"]),
  grade(ex, ["a", "b", "c"]),
  grade(ex, ["c"]),
]));
""",
    )

    exact, partial, superset, miss = results
    assert exact["outcome"] == "correct"
    assert exact["correct"] is True
    assert exact["score"] == 1.0

    assert partial["outcome"] == "partial"
    assert partial["correct"] is False
    assert partial["score"] == 0.5

    # A superset must not receive full credit: Jaccard is 2/3, not 2/2.
    assert superset["outcome"] == "partial"
    assert superset["correct"] is False
    assert superset["score"] == pytest.approx(2 / 3)

    assert miss["outcome"] == "incorrect"
    assert miss["correct"] is False
    assert miss["score"] == 0.0


def test_standalone_artifact_requires_non_empty_string_path(tmp_path: Path) -> None:
    results = _run_core_js(
        tmp_path,
        """
const ex = { type: "artifact", rubric: [{ dimension: "d", weight: 1 }] };
console.log(JSON.stringify([
  grade(ex, { path: "   " }),
  grade(ex, { path: 42 }),
  grade(ex, null),
  grade(ex, { path: " data/run.log ", checked: ["d"] }),
]));
""",
    )

    blank, non_string, missing, valid = results
    for result in (blank, non_string, missing):
        assert result["outcome"] == "incorrect"
        assert result["correct"] is False
        assert result["score"] == 0.0
    assert valid["outcome"] == "submitted"
    assert valid["correct"] is None
    assert valid["score"] == 1.0


def test_standalone_evidence_row_matches_event_schema(tmp_path: Path) -> None:
    row = _run_core_js(
        tmp_path,
        """
const ex = { type: "single_choice", answer: "a", concepts: ["c-one"] };
const result = grade(ex, "a");
console.log(JSON.stringify(
  makeRow("L-ONE", "EX-ONE", ex, "a", result, 2, 15)
));
""",
    )

    required = {
        "id",
        "learner_id",
        "kind",
        "concept_ids",
        "payload",
        "source",
        "created_at",
    }
    assert required <= set(row)
    assert isinstance(row["id"], str) and row["id"]
    assert row["learner_id"] == "local"
    assert row["kind"] == "exercise_attempt"
    assert row["concept_ids"] == ["c-one"]
    assert row["source"] == "standalone"
    assert datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
    assert row["payload"] == {"response": "a", "hints_used": 2, "duration_ms": 15}
    assert row["lesson_id"] == "L-ONE"
    assert row["exercise_id"] == "EX-ONE"
    assert row["outcome"] == "correct"
    assert row["score"] == 1.0
    assert row["max_score"] == 1.0
    assert row["session_id"] is None
    assert row["supersedes"] is None


def test_standalone_row_kind_follows_exercise_type(tmp_path: Path) -> None:
    rows = _run_core_js(
        tmp_path,
        """
const selfAssess = { type: "self_assess", rubric: [{ dimension: "d", weight: 1 }] };
const artifact = { type: "artifact", rubric: [{ dimension: "d", weight: 1 }] };
console.log(JSON.stringify([
  makeRow("L", "E1", selfAssess, { checked: ["d"] }, grade(selfAssess, { checked: ["d"] }), 0, 1),
  makeRow("L", "E2", artifact, { path: "run.log" }, grade(artifact, { path: "run.log" }), 0, 1),
  makeRow("L", "E3", { type: "short_answer", answer: { accepted: ["x"], min_hits: 1 } },
    "x", grade({ type: "short_answer", answer: { accepted: ["x"], min_hits: 1 } }, "x"), 0, 1),
]));
""",
    )

    self_assess_row, artifact_row, short_answer_row = rows
    assert self_assess_row["kind"] == "self_assess"
    assert artifact_row["kind"] == "artifact"
    assert short_answer_row["kind"] == "exercise_attempt"


def test_build_escapes_script_breakout_in_exercise_json(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(FIXTURE, pack)
    exercises_file = pack / "exercises.yaml"
    content = exercises_file.read_text(encoding="utf-8")
    exercises_file.write_text(
        content.replace(
            "prompt: Pick A.",
            "prompt: 'Pick A. </script><script>alert(1)</script> & <b>'",
        ),
        encoding="utf-8",
    )

    paths = build_pack(pack, tmp_path / "dist")
    body = paths[0].read_text(encoding="utf-8")

    assert "</script><script>alert(1)" not in body
    assert "\\u003c/script\\u003e" in body
    assert "\\u003cscript\\u003e" in body
    assert "\\u0026" in body
    assert "\\u003cb\\u003e" in body
    # Only the two template-owned closing tags remain.
    assert body.count("</script>") == 2
