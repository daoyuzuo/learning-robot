# Course Quality Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add teach-skill-inspired quality gates: explicit objective mapping, primary-source and worked-example checks, quiz fairness lint, and author brief templates.

**Architecture:** `LessonManifest` gains an optional `objective_map` (O1 → exercise IDs). A pure `quality/lint.py` evaluates content rules and returns a `LintReport`; `tb lint` prints it and maps to exit codes. Brief templates live in the course-author skill, outside `tb/1` packs.

**Tech Stack:** Python 3.10+, Pydantic v2, dataclasses, argparse, pytest, PyYAML.

**Spec:** [docs/superpowers/specs/2026-11-01-course-quality-gates-design.md](../specs/2026-11-01-course-quality-gates-design.md)

## Global Constraints

- No LLM/network calls in lint.
- Do not change `tb quality` scoring, rendering, or learning runtime.
- `objective_map` is optional; old packs must still load.
- Code identifiers/comments in English; user-facing text and docs in Chinese.
- Do not commit or push; stop after tests.
- Quiz fairness thresholds: position error >70% (only when >=4 choice questions); option length error >3.0, warning >2.0; answer-longest warning >60%.

---

### Task 1: Add optional `objective_map` and map the current course

**Files:**
- Modify: `src/testbridge/contract/models.py`
- Modify: `content-packs/robot-quality-system/modules/*/lessons/*.html` (manifest JSON)
- Test: `tests/test_quality_lint.py`

**Interfaces:**
- Produces: `LessonManifest.objective_map: dict[str, list[str]]`
- Mapping convention: objectives are `O1`, `O2`, ... by list order; each key maps to one or more exercise IDs from `manifest.exercises`.

- [ ] **Step 1: Add the field**

In `LessonManifest`:

```python
    objective_map: dict[str, list[Id]] = Field(default_factory=dict)

    @field_validator("objective_map")
    @classmethod
    def objective_keys(cls, value: dict[str, list[Id]]) -> dict[str, list[Id]]:
        for key, refs in value.items():
            if not re.fullmatch(r"O[1-9]\d*", key):
                raise ValueError("objective_map keys must be O1, O2, ...")
            if not refs:
                raise ValueError("objective_map values must be non-empty")
        return value
```

- [ ] **Step 2: Add a failing loader test**

In `tests/test_quality_lint.py`:

```python
import json
import shutil
from pathlib import Path

from testbridge.content.repository import load_pack

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


def test_objective_map_loads(tmp_path: Path) -> None:
    pack = _copy_minimal(tmp_path)
    lesson = pack / "modules" / "M01" / "lessons" / "L-ONE.html"
    _rewrite_manifest(
        lesson,
        objective_map={"O1": ["EX-ONE"]},
    )
    loaded = load_pack(pack)
    assert loaded.lesson("L-ONE").manifest.objective_map == {"O1": ["EX-ONE"]}
```

- [ ] **Step 3: Run the test**

```bash
.venv/Scripts/python -m pytest tests/test_quality_lint.py::test_objective_map_loads -q
```

Expected: PASS after the model change (before the change it would drop/forbid the field).

- [ ] **Step 4: Map all 21 current lessons**

Run this one-off script from the repo root:

```python
import json
from pathlib import Path

for path in sorted(Path("content-packs/robot-quality-system/modules").glob("*/lessons/*.html")):
    text = path.read_text(encoding="utf-8")
    start = text.index('id="tb-manifest">') + len('id="tb-manifest">')
    end = text.index("</script>", start)
    data = json.loads(text[start:end])
    objectives = data.get("objectives") or []
    exercises = data.get("exercises") or []
    if not objectives or not exercises:
        continue
    mapping = {
        f"O{i + 1}": [
            exercises[min(i, len(exercises) - 1)]
        ]
        for i in range(len(objectives))
    }
    for extra in exercises[len(objectives):]:
        mapping[f"O{len(objectives)}"].append(extra)
    data["objective_map"] = mapping
    block = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(text[:start] + "\n" + block + "\n" + text[end:], encoding="utf-8")
```

- [ ] **Step 5: Re-validate**

```bash
.venv/Scripts/tb.exe validate content-packs/robot-quality-system
```

Expected: `0 error(s), 0 warning(s)`.

---

### Task 2: `tb lint` quality gates

**Files:**
- Create: `src/testbridge/quality/lint.py`
- Modify: `src/testbridge/cli.py`
- Test: `tests/test_quality_lint.py`

**Interfaces:**
- `evaluate_lint(pack: ContentPack) -> LintReport`
- `LintReport.ok`, `.errors`, `.warnings`, `.issues`, `.as_dict()`
- `tb lint <pack> [--json]`, exit 0/1/2.

- [ ] **Step 1: Write failing lint tests**

Append to `tests/test_quality_lint.py`:

```python
from testbridge.cli import main
from testbridge.quality.lint import evaluate_lint


def _codes(report) -> set[str]:
    return {issue.code for issue in report.errors}


def test_lint_minimal_pack_has_warnings_not_errors() -> None:
    report = evaluate_lint(load_pack(MINIMAL))
    assert report.ok
    assert "lint.no_worked_example" in {i.code for i in report.warnings}
    assert "lint.objective_map_missing" in {i.code for i in report.warnings}


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
        "</article>", "<p>TBD</p><p>\"answer\":</p></article>"
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


def test_cli_lint_minimal_exits_0(tmp_path: Path, capsys) -> None:
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_quality_lint.py -q
```

Expected: `ModuleNotFoundError: testbridge.quality.lint` (and CLI `SystemExit: 2`).

- [ ] **Step 3: Implement `quality/lint.py`**

```python
"""Deterministic content lint rules inspired by teaching best practices."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from testbridge.content.repository import ContentPack

_PLACEHOLDER_RE = re.compile(r"(待填|TODO|TBD|example\.com|lorem ipsum)", re.IGNORECASE)
_ANSWER_LEAK_RE = re.compile(r'"(answer|explanation|accepted|rubric)"\s*:')
_UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:ms|s|mm|cm|m/s|m·s|%|°C|kg|Hz|N·m|Nm|N|rad/s|rad|V|A|W)\b"
)
_OBJECTIVE_KEY_RE = re.compile(r"^O[1-9]\d*$")
_REQUIRED_TRUST = {"A", "B"}


@dataclass(frozen=True)
class LintIssue:
    code: str
    message: str
    severity: str = "error"
    lesson_id: str | None = None
    exercise_id: str | None = None

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "lesson_id": self.lesson_id,
            "exercise_id": self.exercise_id,
        }


@dataclass(frozen=True)
class LintReport:
    issues: list[LintIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[LintIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[LintIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }


def _plain_text(body_html: str) -> str:
    return re.sub(r"<[^>]+>", "", body_html)


def _primary_source(pack: ContentPack, lesson):
    for resource_id in lesson.manifest.resources:
        resource = pack.resources.get(resource_id)
        if resource and resource.role == "required" and resource.trust in _REQUIRED_TRUST:
            return resource
    return None


def _check_lesson(pack: ContentPack, lesson) -> list[LintIssue]:
    issues: list[LintIssue] = []
    manifest = lesson.manifest
    level = manifest.target_level
    text = _plain_text(lesson.body_html)

    if _PLACEHOLDER_RE.search(text):
        issues.append(LintIssue("lint.placeholder", "正文包含占位符", "error", manifest.id))
    if _ANSWER_LEAK_RE.search(lesson.body_html):
        issues.append(LintIssue("lint.answer_leak", "正文包含答案/解析字段", "error", manifest.id))

    primary = _primary_source(pack, lesson)
    if primary is None or not primary.why.strip():
        issues.append(LintIssue(
            "lint.primary_source_missing",
            "缺少带 why 的 required A/B 主来源",
            "error",
            manifest.id,
        ))

    if not _UNIT_RE.search(text):
        severity = "error" if level in {"L3", "L4"} else "warning"
        issues.append(LintIssue(
            "lint.no_worked_example",
            "正文没有数字+单位的工程实例",
            severity,
            manifest.id,
        ))

    objectives = [f"O{index + 1}" for index in range(len(manifest.objectives))]
    mapping = manifest.objective_map
    if not mapping:
        severity = "error" if level in {"L3", "L4"} else "warning"
        issues.append(LintIssue(
            "lint.objective_map_missing",
            "缺少 objective_map",
            severity,
            manifest.id,
        ))
    else:
        for objective_id in objectives:
            if not mapping.get(objective_id):
                issues.append(LintIssue(
                    "lint.objective_unmapped",
                    f"{objective_id} 没有映射到练习",
                    "error",
                    manifest.id,
                ))
        for objective_id, exercise_ids in mapping.items():
            if objective_id not in objectives:
                issues.append(LintIssue(
                    "lint.objective_unknown",
                    f"{objective_id} 不在 objectives 范围内",
                    "error",
                    manifest.id,
                ))
            for exercise_id in exercise_ids:
                if exercise_id not in manifest.exercises:
                    issues.append(LintIssue(
                        "lint.objective_exercise_unknown",
                        f"{objective_id} 引用了本课未列出的 {exercise_id}",
                        "error",
                        manifest.id,
                    ))
    return issues


def _check_quiz(pack: ContentPack) -> list[LintIssue]:
    issues: list[LintIssue] = []
    choice = [
        exercise
        for exercise in pack.exercises.values()
        if exercise.type in {"single_choice", "multi_choice"}
    ]
    if not choice:
        return issues

    positions: Counter[str] = Counter()
    longest_correct = 0
    for exercise in choice:
        option_ids = [option.id for option in exercise.options]
        if exercise.type == "single_choice":
            index = option_ids.index(exercise.answer)
        else:
            index = min(option_ids.index(answer) for answer in exercise.answer)
        positions[option_ids[index]] += 1

        lengths = [len(option.text) for option in exercise.options]
        if lengths[index] == max(lengths):
            longest_correct += 1
        ratio = max(lengths) / min(lengths) if min(lengths) else 0
        if ratio > 3.0:
            issues.append(LintIssue(
                "lint.quiz_option_length",
                f"选项长度比 {ratio:.1f} > 3.0",
                "error",
                exercise_id=exercise.id,
            ))
        elif ratio > 2.0:
            issues.append(LintIssue(
                "lint.quiz_option_length",
                f"选项长度比 {ratio:.1f} > 2.0",
                "warning",
                exercise_id=exercise.id,
            ))

    if len(choice) >= 4:
        max_share = max(positions.values()) / len(choice)
        if max_share > 0.7:
            issues.append(LintIssue(
                "lint.quiz_answer_position",
                f"单一正确位置占比 {max_share:.0%} > 70%",
                "error",
            ))

    if longest_correct / len(choice) > 0.6:
        issues.append(LintIssue(
            "lint.quiz_answer_longest",
            f"正确答案为最长选项占比 {longest_correct / len(choice):.0%} > 60%",
            "warning",
        ))
    return issues


def evaluate_lint(pack: ContentPack) -> LintReport:
    issues: list[LintIssue] = []
    for lesson in pack.lessons_in_order():
        issues.extend(_check_lesson(pack, lesson))
    issues.extend(_check_quiz(pack))
    return LintReport(issues=issues)
```

- [ ] **Step 4: Add `tb lint` CLI**

In `cli.py`, add after `_run_depth`:

```python
def _run_lint(pack_dir: Path, as_json: bool) -> int:
    from testbridge.quality.lint import evaluate_lint

    try:
        pack = load_pack(pack_dir)
    except ContentValidationError as exc:
        for issue in exc.report.errors:
            print(f"ERROR {issue.code}: {issue.message}")
        print("run tb validate first")
        return 2

    report = evaluate_lint(pack)
    if as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        for issue in report.errors:
            target = issue.lesson_id or issue.exercise_id or ""
            print(f"ERROR {issue.code}: {issue.message} {target}".rstrip())
        for issue in report.warnings:
            target = issue.lesson_id or issue.exercise_id or ""
            print(f"WARN {issue.code}: {issue.message} {target}".rstrip())
        print(
            f"lint: {len(report.errors)} error(s), "
            f"{len(report.warnings)} warning(s)"
        )
    return 0 if report.ok else 1
```

Add parser after `depth`:

```python
    lint = sub.add_parser("lint", help="check content quality rules")
    lint.add_argument("pack")
    lint.add_argument("--json", action="store_true")
```

Add dispatch before `depth`:

```python
    if args.command == "lint":
        return _run_lint(Path(args.pack), args.json)
```

- [ ] **Step 5: Run lint tests**

```bash
.venv/Scripts/python -m pytest tests/test_quality_lint.py -q
```

Expected: all pass.

- [ ] **Step 6: Run `tb lint` on the real course**

```bash
.venv/Scripts/tb.exe lint content-packs/robot-quality-system
```

Expected: fix any errors/warnings in Task 3 until exit 0.

---

### Task 3: Brief templates, skill wiring, content fixes, acceptance

**Files:**
- Create: `.claude/skills/course-author/references/mission-brief.md`
- Create: `.claude/skills/course-author/references/lesson-brief.md`
- Modify: `.claude/skills/course-author/SKILL.md`
- Modify: `.claude/skills/course-author/references/authoring-guide.md`
- Modify: `CLAUDE.md`
- Modify: `docs/ROADMAP.md`
- Modify: `content-packs/robot-quality-system/exercises.yaml` (quiz fairness fixes)
- Create: `docs/course-briefs/robot-quality-system/MISSION.md`
- Create: `docs/course-briefs/robot-quality-system/RESOURCES.md`
- Create: `docs/course-briefs/robot-quality-system/LESSON-BRIEFS.md`

- [ ] **Step 1: Write the brief templates**

`mission-brief.md` mirrors teach's `MISSION-FORMAT.md`:

```markdown
# MISSION.md Format

存放于 `docs/course-briefs/<pack>/MISSION.md`，是课程所有取舍的根据。

## Template

# Mission: {Topic}

## Why
{1-3 句。具体的工作/生活目标；不要写“理解 X”，写“能用 X 完成 Y”。}

## Success looks like
- {可观察的成果 1}
- {可观察的成果 2}

## Constraints
- {时间、基础、目标岗位、评估方式}

## Out of scope
- {明确不讲的相邻主题，保护最近发展区}
```

`lesson-brief.md`:

```markdown
# Lesson Brief Format

每课一页，放在 `docs/course-briefs/<pack>/lessons/<lesson-id>.md`。

## Template

# {Lesson title}

## Tangible win
{学完能独立完成的一件具体事情，一句话。}

## Primary source
{RESOURCES.md 中的一条 A/B 来源，以及本课用它的哪一部分。}

## Retrieval
- {来自先修概念的 2-3 道回忆题}

## Worked example
{带数字/单位的完整示例，含条件、步骤、结果。}

## Exercises
| Objective | Exercise | Misconception |
|---|---|---|
| O1 | EX-... | ... |

## Figure / table
{1 张表或图，说明它表达的关系。}

## Minutes
{45-60}
```

- [ ] **Step 2: Update the course-author skill**

In `SKILL.md`, before "设计结构", add:

```markdown
2.5 **先写作者 brief**：在 `docs/course-briefs/<id>/` 写 `MISSION.md`、
   `RESOURCES.md` 和每课 `lessons/<lesson-id>.md`。MISSION 未写清 Why / Success /
   Out of scope 前，不要开始写正文。
```

Change the validation loop to include `tb lint`:

```text
   - `tb validate content-packs/<id>` —— 硬契约；必须 0 error。
   - `tb depth content-packs/<id>` —— 深度门禁；必须 0 error。
   - `tb lint content-packs/<id>` —— 内容门禁；必须 0 error。
   - `tb quality content-packs/<id>` —— 可选建议。
   - `tb build content-packs/<id> --out dist` —— 渲染检查。
```

Add references to `mission-brief.md` and `lesson-brief.md` near the top.

- [ ] **Step 3: Update authoring guide**

Add a section "0. 先写 Mission 与 Lesson brief" with the two templates and the rule
"没有 primary source、worked example、objective_map 的课不要交付".

- [ ] **Step 4: Update CLAUDE.md and ROADMAP**

- `CLAUDE.md` 工作方式：课程创作改完跑 `tb validate`、`tb depth`、`tb lint`、`tb build`。
- `CLAUDE.md` 完成定义：增加 `tb lint content-packs/<id>` 通过。
- `ROADMAP.md` 增加 "2026-11-01 课程质量门禁" 小节，引用本 spec。

- [ ] **Step 5: Fix current course lint violations**

Run:

```bash
.venv/Scripts/tb.exe lint content-packs/robot-quality-system
```

Fix all errors. Expected fixes:
- Quiz option length > 3.0: balance option text in EX-005-01, EX-011-01,
  EX-018-01, EX-019-01, EX-020-01, EX-008-01, EX-006-01.
- Any missing worked examples: add a numeric example.
- Any objective_map issues: rerun the Task 1 script if a lesson was added.

Do not weaken thresholds to make the course pass.

- [ ] **Step 6: Write the current course briefs**

Create `docs/course-briefs/robot-quality-system/MISSION.md` using the template,
with:
- Why: 为具身智能/机器人测试岗位建立可落地的质量体系，能独立写测试策略、
  风险和认证方案。
- Success: 能为一个机器人产品写质量方案；能选标准组合；能设计可复现实验。
- Constraints: 21 课、1,095 分钟、中文、工程实例优先。
- Out of scope: 具体代码实现、ROS 2 编程、硬件设计。

Create `RESOURCES.md` with Knowledge/Wisdom/Gaps, reusing the 34 resources from
`resources.yaml` grouped by module, and listing gaps (e.g., 缺少真实事故数据、
缺少部分标准全文访问).

Create `LESSON-BRIEFS.md` with one row per lesson: lesson id, tangible win,
primary source, exercise count.

- [ ] **Step 7: Acceptance**

```bash
.venv/Scripts/tb.exe lint content-packs/robot-quality-system
.venv/Scripts/tb.exe depth content-packs/robot-quality-system
.venv/Scripts/tb.exe validate content-packs/robot-quality-system
.venv/Scripts/tb.exe quality content-packs/robot-quality-system
.venv/Scripts/tb.exe build content-packs/robot-quality-system --out dist
.venv/Scripts/python -m pytest -q
```

Expected: lint/depth 0 error; validate 0/0; quality 100/100; build 21 lessons;
full pytest passes. Report exact outputs. Do not commit.
