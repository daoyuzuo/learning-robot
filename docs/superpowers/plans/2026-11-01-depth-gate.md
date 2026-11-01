# Depth Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic `tb depth` command that rejects lessons below per-level length/structure thresholds, so outline-style short courses cannot pass the authoring workflow.

**Architecture:** A pure evaluator in `quality/depth.py` takes an already-loaded `ContentPack`, counts body characters after stripping HTML tags, counts `<h2>`/`<table>`/`<figure>`/manifest exercises, and returns a `DepthReport`. A thin CLI handler prints per-lesson results and maps the report to exit codes. `tb validate` and `tb quality` keep their current semantics.

**Tech Stack:** Python 3.10+, dataclasses, `html.parser.HTMLParser`, argparse, pytest.

**Spec:** [docs/superpowers/specs/2026-11-01-depth-gate-design.md](../specs/2026-11-01-depth-gate-design.md)

## Global Constraints

- Do not change `tb/1` models, validator behavior, or `tb quality` scoring.
- Do not add dependencies, network calls, or LLM calls.
- Code identifiers/comments in English; user-facing CLI text and docs in Chinese.
- Do not run `git commit` or `git push`; stop after tests and report results. The user decides when to commit.
- Thresholds are exactly: L1 1200/3/0/2, L2 2000/4/0/2, L3 3500/6/1/2, L4 4500/7/1/2
  (chars / `<h2>` / tables+figures / exercises).

---

### Task 1: Depth evaluator

**Files:**
- Create: `src/testbridge/quality/depth.py`
- Test: `tests/test_quality_depth.py`

**Interfaces:**
- Consumes: `testbridge.content.repository.ContentPack`, `testbridge.content.repository.load_pack`
- Produces:
  - `body_char_count(body_html: str) -> int`
  - `evaluate_depth(pack: ContentPack) -> DepthReport`
  - `DepthReport.ok: bool`, `DepthReport.errors: list[DepthIssue]`, `DepthReport.lessons: list[LessonDepth]`
  - `LessonDepth.lesson_id/level/chars/sections/tables/figures/exercises/issues/ok`
  - `DepthIssue.code/message/lesson_id`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_quality_depth.py`:

```python
import json
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
    text = text.replace('"target_level": "L2"', f'"target_level": "{level}"')
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/Scripts/python -m pytest tests/test_quality_depth.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'testbridge.quality.depth'`.

- [ ] **Step 3: Implement the evaluator**

Create `src/testbridge/quality/depth.py`:

```python
"""Deterministic lesson depth checks.

This module answers "is this lesson substantial enough to teach from?" and is
deliberately separate from the tb/1 contract and the quality score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from testbridge.content.repository import ContentPack

DEFAULT_MIN_CHARS: dict[str, int] = {
    "L1": 1200,
    "L2": 2000,
    "L3": 3500,
    "L4": 4500,
}
DEFAULT_MIN_SECTIONS: dict[str, int] = {
    "L1": 3,
    "L2": 4,
    "L3": 6,
    "L4": 7,
}
DEFAULT_MIN_VISUALS: dict[str, int] = {
    "L1": 0,
    "L2": 0,
    "L3": 1,
    "L4": 1,
}
MIN_EXERCISES = 2

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


class _StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections = 0
        self.tables = 0
        self.figures = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower == "h2":
            self.sections += 1
        elif lower == "table":
            self.tables += 1
        elif lower == "figure":
            self.figures += 1

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)


def body_char_count(body_html: str) -> int:
    """Count non-whitespace characters after removing HTML tags."""
    return len(_WHITESPACE_RE.sub("", _TAG_RE.sub("", body_html)))


def _structure(body_html: str) -> tuple[int, int, int]:
    parser = _StructureParser()
    parser.feed(body_html)
    parser.close()
    return parser.sections, parser.tables, parser.figures


@dataclass(frozen=True)
class DepthIssue:
    code: str
    message: str
    lesson_id: str

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "lesson_id": self.lesson_id,
        }


@dataclass(frozen=True)
class LessonDepth:
    lesson_id: str
    level: str
    chars: int
    sections: int
    tables: int
    figures: int
    exercises: int
    issues: list[DepthIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def as_dict(self) -> dict:
        return {
            "lesson_id": self.lesson_id,
            "level": self.level,
            "chars": self.chars,
            "sections": self.sections,
            "tables": self.tables,
            "figures": self.figures,
            "exercises": self.exercises,
            "ok": self.ok,
            "issues": [issue.as_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class DepthReport:
    lessons: list[LessonDepth] = field(default_factory=list)

    @property
    def errors(self) -> list[DepthIssue]:
        return [issue for lesson in self.lessons for issue in lesson.issues]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "lessons": [lesson.as_dict() for lesson in self.lessons],
            "errors": [issue.as_dict() for issue in self.errors],
        }


def evaluate_depth(pack: ContentPack) -> DepthReport:
    lessons: list[LessonDepth] = []
    for lesson in pack.lessons_in_order():
        manifest = lesson.manifest
        level = manifest.target_level
        chars = body_char_count(lesson.body_html)
        sections, tables, figures = _structure(lesson.body_html)
        exercises = len(manifest.exercises)
        issues: list[DepthIssue] = []

        min_chars = DEFAULT_MIN_CHARS[level]
        if chars < min_chars:
            issues.append(DepthIssue(
                "depth.lesson_too_short",
                f"{chars} < {min_chars}",
                manifest.id,
            ))

        min_sections = DEFAULT_MIN_SECTIONS[level]
        if sections < min_sections:
            issues.append(DepthIssue(
                "depth.too_few_sections",
                f"{sections} < {min_sections}",
                manifest.id,
            ))

        min_visuals = DEFAULT_MIN_VISUALS[level]
        visuals = tables + figures
        if visuals < min_visuals:
            issues.append(DepthIssue(
                "depth.no_table_or_figure",
                f"{visuals} < {min_visuals}",
                manifest.id,
            ))

        if exercises < MIN_EXERCISES:
            issues.append(DepthIssue(
                "depth.too_few_exercises",
                f"{exercises} < {MIN_EXERCISES}",
                manifest.id,
            ))

        lessons.append(LessonDepth(
            lesson_id=manifest.id,
            level=level,
            chars=chars,
            sections=sections,
            tables=tables,
            figures=figures,
            exercises=exercises,
            issues=issues,
        ))
    return DepthReport(lessons=lessons)
```

- [ ] **Step 4: Run tests to verify the evaluator passes**

Run:

```bash
.venv/Scripts/python -m pytest tests/test_quality_depth.py -q
```

Expected: the four evaluator tests pass; the three `test_cli_depth_*` tests still fail because the CLI command does not exist yet.

---

### Task 2: `tb depth` CLI

**Files:**
- Modify: `src/testbridge/cli.py` (parser around line 330; handler near `_run_quality`)
- Test: `tests/test_quality_depth.py` (CLI tests already written in Task 1)

**Interfaces:**
- Consumes: `evaluate_depth` from Task 1; `ContentValidationError`, `load_pack` already imported in `cli.py`.
- Produces: `tb depth <pack> [--json]`, exit codes 0/1/2.

- [ ] **Step 1: Run the CLI tests to verify they fail for the right reason**

Run:

```bash
.venv/Scripts/python -m pytest tests/test_quality_depth.py::test_cli_depth_fails_on_minimal -q
```

Expected: `SystemExit: 2` because argparse rejects the unknown `depth` command.

- [ ] **Step 2: Add the handler**

In `src/testbridge/cli.py`, add after `_run_quality` (around line 149):

```python
def _run_depth(pack_dir: Path, as_json: bool) -> int:
    from testbridge.quality.depth import evaluate_depth

    try:
        pack = load_pack(pack_dir)
    except ContentValidationError as exc:
        for issue in exc.report.errors:
            print(f"ERROR {issue.code}: {issue.message}")
        print("run tb validate first")
        return 2

    report = evaluate_depth(pack)
    if as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        for lesson in report.lessons:
            status = "OK" if lesson.ok else "FAIL"
            print(
                f"{status:<4} {lesson.lesson_id} {lesson.level} "
                f"chars={lesson.chars} h2={lesson.sections} "
                f"tables={lesson.tables} figures={lesson.figures} "
                f"exercises={lesson.exercises}"
            )
            for issue in lesson.issues:
                print(f"     {issue.code}: {issue.message}")
        print(f"{len(report.lessons)} lesson(s), {len(report.errors)} error(s)")
    return 0 if report.ok else 1
```

- [ ] **Step 3: Add the parser**

In `src/testbridge/cli.py`, after the `quality` parser block (around line 337):

```python
    depth = sub.add_parser("depth", help="check lesson depth")
    depth.add_argument("pack")
    depth.add_argument("--json", action="store_true")
```

- [ ] **Step 4: Add dispatch**

In `src/testbridge/cli.py`, before the `quality` dispatch block (around line 437):

```python
    if args.command == "depth":
        return _run_depth(Path(args.pack), args.json)
```

- [ ] **Step 5: Run the depth tests**

Run:

```bash
.venv/Scripts/python -m pytest tests/test_quality_depth.py -q
```

Expected: all 7 tests pass.

- [ ] **Step 6: Run the existing CLI/quality tests**

Run:

```bash
.venv/Scripts/python -m pytest tests/test_cli.py tests/test_cli_quality.py tests/test_cli_p2.py -q
```

Expected: all pass, no behavior change to `validate`/`quality`.

---

### Task 3: Authoring contract and acceptance

**Files:**
- Modify: `.claude/skills/course-author/SKILL.md`
- Modify: `.claude/skills/course-author/references/authoring-guide.md`
- Modify: `CLAUDE.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Update the skill validation loop**

In `.claude/skills/course-author/SKILL.md`, replace the validation loop with:

```text
6. **校验循环**：
   - `tb validate content-packs/<id>` —— 硬契约；必须 0 error。
   - `tb depth content-packs/<id>` —— 深度门禁；必须 0 error。
   - `tb quality content-packs/<id>` —— 可选建议；按需改进，不绕过 validate/depth。
   - `tb build content-packs/<id> --out dist` —— 渲染检查。
   - 交付时给出 `tb serve content-packs/<id> --port 8000 --open`。
```

Add a new section after "必须遵守的硬契约":

```markdown
## 深度契约

每课必须达到 `tb depth` 的默认阈值：

| 级别 | 最少字数 | 最少 `<h2>` | 最少表格/图 | 最少练习 |
|---|---|---|---|---|
| L1 | 1,200 | 3 | 0 | 2 |
| L2 | 2,000 | 4 | 0 | 2 |
| L3 | 3,500 | 6 | 1 | 2 |
| L4 | 4,500 | 7 | 1 | 2 |

“字数”是正文去标签、去空白后的字符数，不含 manifest。`tb depth` 失败时不要交付；
先补工程场景、方法步骤、数字实例、判定证据、误区或检查表，不要灌水。
```

- [ ] **Step 2: Update the authoring guide**

In `.claude/skills/course-author/references/authoring-guide.md`, after section 3
("结构自由，教学优先"), add:

```markdown
## 3.1 深度下限

- 每课至少达到 `tb depth` 的级别阈值（L3 默认 3,500 字、6 个 `<h2>`、1 个表格/图、2 道练习）。
- 一节完整的课应包含：工程场景、概念与边界、方法步骤、机器人实例与数字、判定与证据、
  常见误区、检查清单、小结。
- 交付前必须跑 `tb depth`；少于阈值时补实质内容，不要用重复段落凑字数。
```

- [ ] **Step 3: Update CLAUDE.md**

In `CLAUDE.md` → `## 工作方式`, replace the course-authoring bullet's validation
sentence with:

```markdown
- **课程创作：** 读 `.claude/skills/course-author/SKILL.md`，用 `tb scaffold` 起步，
  直接写 `content-packs/`；不要在框架内新增生成器/LLM 流水线。改完跑 `tb validate`、
  `tb depth`、`tb build`。
```

In `## 完成定义（P2）`, add:

```markdown
- `tb depth content-packs/<id>` 通过：每课达到级别对应的字数、结构、图示和练习阈值
```

- [ ] **Step 4: Update ROADMAP.md**

After the "2026-11-01 架构转向：Skill 驱动课程创作" section, add:

```markdown
## 2026-11-01 课程深度门禁 — 已完成

- 新增 `tb depth <pack>`：按 L1–L4 阈值检查每课正文去标签字数、`<h2>` 数、
  表格/图示数和练习数；失败退出 1。
- `tb validate` / `tb quality` 语义不变；深度门禁独立，避免契约与评分耦合。
- 作者 skill 与 authoring guide 增加深度契约；交付前必须 `tb validate` + `tb depth`。
- 设计见 [课程深度门禁](superpowers/specs/2026-11-01-depth-gate-design.md)。
- 验证：`tb depth content-packs/robot-quality-system` 0 error；
  `pytest` 全绿。
```

- [ ] **Step 5: Run acceptance**

```bash
.venv/Scripts/tb.exe depth content-packs/robot-quality-system
```

Expected: exit 0, `21 lesson(s), 0 error(s)`.

```bash
.venv/Scripts/tb.exe depth tests/fixtures/packs/sample-sensors
```

Expected: exit 1, with `depth.lesson_too_short` (fixtures are exempt from delivery).

```bash
.venv/Scripts/tb.exe validate content-packs/robot-quality-system
.venv/Scripts/tb.exe quality content-packs/robot-quality-system
```

Expected: `0 error(s), 0 warning(s)` and `quality: 100/100`.

```bash
.venv/Scripts/python -m pytest -q
```

Expected: full suite passes.

- [ ] **Step 6: Report**

Report the exact outputs of Step 5. Do not commit.
