"""Build standalone, offline HTML lessons."""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.lesson.renderer import render_lesson

STANDALONE_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__</style>
</head>
<body data-lesson-id="__LESSON_ID__">
<main class="tb-main tb-lesson-main">
__BODY__
<button id="tb-export">导出证据 JSONL</button>
</main>
<script>const TB_EXERCISES = __DATA__; const TB_LESSON_ID = "__LESSON_ID__";</script>
<script>__JS__</script>
</body>
</html>
"""

# Shared grading and evidence-row logic. Kept outside the IIFE so the exact
# browser behaviour can be exercised directly by the build tests.
STANDALONE_CORE_JS = r"""
function norm(value) {
  return String(value || "").toLowerCase().replace(/[\s,，。.!！?？;；:：、"'“”‘’()（）\[\]【】]/g, "");
}
function grade(ex, response) {
  if (ex.type === "single_choice") {
    const ok = response === ex.answer;
    return { outcome: ok ? "correct" : "incorrect", correct: ok, score: ok ? 1 : 0, max_score: 1,
             feedback: ok ? "回答正确。" : "再想想。" };
  }
  if (ex.type === "multi_choice") {
    const expected = new Set(ex.answer || []);
    const selected = new Set(Array.isArray(response) ? response : []);
    const hits = Array.from(expected).filter((item) => selected.has(item)).length;
    const union = new Set([...expected, ...selected]).size;
    const score = union ? hits / union : 0;
    const ok = hits === expected.size && selected.size === expected.size;
    return { outcome: ok ? "correct" : (hits ? "partial" : "incorrect"), correct: ok, score: score, max_score: 1,
             feedback: ok ? "全对。" : "命中了 " + hits + "/" + expected.size + " 个正确项。" };
  }
  if (ex.type === "short_answer") {
    const text = norm(response);
    const accepted = (ex.answer && ex.answer.accepted) || [];
    const matched = accepted.filter((item) => text.includes(norm(item)));
    const minHits = (ex.answer && ex.answer.min_hits) || 1;
    const ok = matched.length >= minHits;
    return { outcome: ok ? "correct" : "incorrect", correct: ok, score: accepted.length ? matched.length / accepted.length : 0, max_score: 1,
             feedback: ok ? "命中关键点。" : "关键点不足。" };
  }
  if (ex.type === "self_assess") {
    const checked = new Set((response && response.checked) || []);
    const score = (ex.rubric || []).reduce((sum, item) => sum + (checked.has(item.dimension) ? item.weight : 0), 0);
    return { outcome: "submitted", correct: null, score: score, max_score: 1, feedback: "已记录自评。" };
  }
  const path = response && typeof response.path === "string" ? response.path.trim() : "";
  if (!path) {
    return { outcome: "incorrect", correct: false, score: 0, max_score: 1, feedback: "请填写附件路径。" };
  }
  const checked = new Set((response && response.checked) || []);
  const score = (ex.rubric || []).reduce((sum, item) => sum + (checked.has(item.dimension) ? item.weight : 0), 0);
  return { outcome: "submitted", correct: null, score: score, max_score: 1, feedback: "已记录产出物。" };
}
function makeRow(lessonId, exerciseId, exercise, response, result, hintsUsed, durationMs) {
  const kind = exercise.type === "self_assess" ? "self_assess"
    : exercise.type === "artifact" ? "artifact"
    : "exercise_attempt";
  return {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2),
    learner_id: "local",
    kind: kind,
    concept_ids: exercise.concepts || [],
    payload: { response: response, hints_used: hintsUsed, duration_ms: durationMs },
    source: "standalone",
    created_at: new Date().toISOString(),
    session_id: null,
    lesson_id: lessonId,
    exercise_id: exerciseId,
    outcome: result.outcome,
    score: result.score,
    max_score: result.max_score,
    supersedes: null,
  };
}
"""

STANDALONE_JS = (
    r"""
(function () {
  const KEY = "tb-evidence";
  let memory = null;
  function load() {
    if (memory !== null) { return memory.slice(); }
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; }
  }
  function showStorageWarning() {
    if (document.getElementById("tb-storage-warning")) { return; }
    const warning = document.createElement("p");
    warning.id = "tb-storage-warning";
    warning.textContent = "未检测到本地存储，证据仅保留在本次会话，请立即导出。";
    const button = document.getElementById("tb-export");
    if (button && button.parentNode) { button.parentNode.insertBefore(warning, button); }
  }
  function save(rows) {
    try {
      localStorage.setItem(KEY, JSON.stringify(rows));
      memory = null;
    } catch (e) {
      memory = rows.slice();
      showStorageWarning();
    }
  }
"""
    + STANDALONE_CORE_JS
    + r"""
  document.querySelectorAll("form.tb-exercise").forEach((form) => {
    const startedAt = Date.now();
    let hintsUsed = 0;
    const hintButton = form.querySelector(".tb-hint-button");
    if (hintButton) {
      hintButton.addEventListener("click", () => {
        const next = Array.from(form.querySelectorAll(".tb-hint[hidden]"))[0];
        if (next) { next.hidden = false; hintsUsed += 1; }
        else { hintButton.disabled = true; hintButton.textContent = "没有更多提示"; }
      });
    }
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const type = form.dataset.exerciseType;
      let response = null;
      if (type === "single_choice") {
        const el = form.querySelector('input[name="answer"]:checked');
        response = el ? el.value : null;
      } else if (type === "multi_choice") {
        response = Array.from(form.querySelectorAll('input[name="answer"]:checked')).map((el) => el.value);
      } else if (type === "short_answer") {
        response = form.querySelector('textarea[name="answer"]').value;
      } else if (type === "self_assess") {
        response = { checked: Array.from(form.querySelectorAll('input[name="checked"]:checked')).map((el) => el.value) };
      } else {
        response = {
          path: form.querySelector('input[name="path"]').value,
          notes: form.querySelector('textarea[name="notes"]').value,
          checked: Array.from(form.querySelectorAll('input[name="checked"]:checked')).map((el) => el.value),
        };
      }
      const exercise = TB_EXERCISES[form.dataset.exerciseId];
      const result = grade(exercise, response);
      const feedback = form.querySelector(".tb-feedback");
      feedback.hidden = false;
      feedback.dataset.outcome = result.outcome;
      feedback.textContent = result.feedback;
      const rows = load();
      rows.push(makeRow(
        TB_LESSON_ID,
        form.dataset.exerciseId,
        exercise,
        response,
        result,
        hintsUsed,
        Date.now() - startedAt,
      ));
      save(rows);
      form.querySelector('button[type="submit"]').disabled = true;
    });
  });
  document.getElementById("tb-export").addEventListener("click", () => {
    const lines = load().map((row) => JSON.stringify(row)).join("\n") + "\n";
    const blob = new Blob([lines], { type: "application/x-ndjson" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "tb-evidence.jsonl";
    link.click();
  });
  document.querySelectorAll(".tb-widget").forEach((widget) => {
    const template = widget.querySelector("template.tb-widget-template");
    const canvas = widget.querySelector(".tb-widget-canvas");
    if (!template || !canvas) return;
    const inputs = Array.from(widget.querySelectorAll("input[data-param]"));
    function render() {
      let markup = template.innerHTML;
      inputs.forEach((input) => {
        markup = markup.split("{{" + input.dataset.param + "}}").join(input.value);
        const output = input.parentElement.querySelector("output");
        if (output) output.textContent = input.value;
      });
      canvas.innerHTML = markup;
    }
    inputs.forEach((input) => input.addEventListener("input", render));
    render();
  });
})();
"""
)


def _script_json(value: object) -> str:
    """Serialize JSON so it cannot terminate its ``<script>`` container."""
    serialized = json.dumps(value, ensure_ascii=False)
    return (
        serialized.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _render_document(values: dict[str, str]) -> str:
    return re.sub(
        r"__(TITLE|LESSON_ID|CSS|DATA|JS|BODY)__",
        lambda match: values[match.group(1)],
        STANDALONE_TEMPLATE,
    )


def build_pack(pack_dir: Path, out_dir: Path, lesson_id: str | None = None) -> list[Path]:
    pack = load_pack(pack_dir)
    target_root = out_dir / pack.meta.id
    lessons = [pack.lessons[lesson_id]] if lesson_id else pack.lessons_in_order()
    css = (Path(__file__).resolve().parents[2] / "web" / "static" / "tb.css").read_text(
        encoding="utf-8"
    )

    written: list[Path] = []
    for lesson in lessons:
        view = render_lesson(pack, lesson.manifest.id)
        relative = Path("modules") / lesson.manifest.module / "lessons" / f"{lesson.manifest.id}.html"
        path = target_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {exercise.id: exercise.model_dump(mode="json") for exercise in view.exercises}
        values = {
            "TITLE": html.escape(lesson.manifest.title),
            "LESSON_ID": lesson.manifest.id,
            "CSS": css,
            "DATA": _script_json(data),
            "JS": STANDALONE_JS,
            "BODY": view.body_html,
        }
        document = _render_document(values)
        path.write_text(document, encoding="utf-8")
        written.append(path)

    assets = pack.root / "assets"
    if assets.is_dir():
        shutil.copytree(assets, target_root / "assets", dirs_exist_ok=True)

    manifest = {
        "pack": pack.meta.model_dump(mode="json", by_alias=True),
        "lessons": [item.manifest.id for item in lessons],
    }
    (target_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return written
