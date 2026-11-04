# 课程体系重排、讲评范围与呈现形式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `robot-quality-system` 重排为 4 模块 22 课（新增 SIL/HIL 课），让讲评只围绕本次提交的题目，并让课程正文按需使用图/代码块/提示块。

**Architecture:** 先做 3 个小的引擎改动（讲评上下文收敛、`data-tone` 白名单、`lint.lesson_order` 门禁），每一处都先写失败测试；再做纯数据重排（ID 迁移表 + 新课 + 格式扩写）；最后更新文档并跑全部门禁。有学习证据的 3 个练习 ID 保持不动，因此不做证据迁移。

**Tech Stack:** Python 3.10+、Pydantic v2、FastAPI、Jinja2、pytest、`tb` CLI（validate/depth/lint/build）、纯数据 `tb/1` YAML + HTML 片段。

**Spec:** `docs/superpowers/specs/2026-11-04-course-restructure-and-review-scope-design.md`

## Global Constraints

- 内容包只能含 `tb/1` 数据，**不得** import 引擎代码；引擎不得写死学科文本。
- 不改判分、掌握度、调度、证据语义；不升 `tb/1` 契约版本（只加白名单属性与可选参数）。
- 净化器继续禁止 `script`/`style`/`iframe`/`on*`/不安全 URL 方案。
- 全部校验命令用 `.venv/Scripts/python.exe -m testbridge.cli <cmd>` 运行（本机 venv 未安装包）。
- 交付前必须跑：`validate` → `depth` → `lint` → `build` → 全量 `pytest`，并贴出真实输出。
- 不修改 `tests/fixtures/packs/*` 的内容（其它测试依赖它们）。
- 已知基线失败：`tests/test_css_tokens.py::test_reading_measure_and_legacy_class_hooks_survive`（上一轮双栏改版遗留，工作开始前即失败）。本次不主动修，交付时如实报告是否仍失败。

## Review Focus

- **讲评上下文只含一题**：一道 3 练习题目的课，讲评第 2 题时提示词里不能出现第 1、3 题的题干或选项——否则模型会重复“另一题没做”的旧行为。
- **缓存版本失配**：数据库里已存在 `prompt_version=review/1` 的旧讲评时，请求必须重新生成而不是直接返回旧讲评（否则修复对历史数据无效）。
- **提示块白名单只放开展示属性**：加 `data-tone` 后，`style="..."`、`onclick="..."`、`javascript:` URL 仍必须被剥除/拒绝。
- **课序与先修一致性**：任何课只要遍历到一个“在更晚才教”的先修概念，`tb lint` 必须报 `lint.lesson_order`，且工作区现有两个 fixture 包和重排后的包都必须通过。
- **练习挂载与 manifest 同步改名**：改 `EX-*` ID 时正文挂载点与 manifest `exercises` 任一漏改都应被 `tb validate` 拦下，而不是静默丢题。

---

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `src/testbridge/tutor/context.py` | 课程上下文（正文/概念/资源/练习题干） | 改：`build_context` 增加 `exercise_ids` 参数 |
| `src/testbridge/tutor/review.py` | 讲评上下文与提示词 | 改：只放本次题目；提示词加规则；`PROMPT_VERSION` 由 service 持有 |
| `src/testbridge/tutor/review_service.py` | 讲评编排 | 改：`PROMPT_VERSION = "review/2"`；缓存命中加版本判断 |
| `src/testbridge/contract/sanitize.py` | HTML 白名单 | 改：`data-tone` 进 `ALLOWED_ATTRIBUTES["*"]` |
| `src/testbridge/quality/lint.py` | 确定性内容门禁 | 改：新增 `lint.lesson_order` |
| `content-packs/robot-quality-system/concepts.yaml` | 概念图 | 改：新增 `sil-hil-validation`；`quality-system-synthesis` 补先修 |
| `content-packs/robot-quality-system/exercises.yaml` | 45 → 49 道练习 | 改：按迁移表改名 + 新增 3 道 |
| `content-packs/robot-quality-system/modules/M0{1..4}/module.yaml` | 模块与课序 | 改：3 模块 → 4 模块 |
| `content-packs/robot-quality-system/modules/*/lessons/*.html` | 21 课 → 22 课 | 改：移动/改名/改写 |
| `content-packs/robot-quality-system/assets/figures/*.svg` | 本地 SVG 图 | 增 |
| `docs/course-briefs/robot-quality-system/{MISSION,LESSON-BRIEFS}.md` | 作者 brief | 改 |
| `.claude/skills/course-author/{SKILL.md,references/*}` | 重排流程 | 改 |
| `docs/ROADMAP.md` | 全局路线图 | 改：记录本次 |

---

## 迁移表（Task 6–9 的唯一事实来源）

**课 ID 与练习 ID**

| 新课 ID | 标题 | 旧课 ID | 新课练习题 | 旧练习 ID |
|---|---|---|---|---|
| L-001-001 | 测试策略的输入与边界 | L-001-001 | EX-001-01, EX-001-02 | 同（不变） |
| L-001-002 | 风险分级与风险驱动测试 | L-001-002 | EX-002-01, EX-002-02 | 同（不变） |
| L-001-003 | 通用测试标准地图：29119 与 ISTQB | L-003-001 | EX-003-01, EX-003-02 | EX-015-01, EX-015-02 |
| L-001-004 | 机器人安全标准族：从工业到服务 | L-003-003 | EX-004-01, EX-004-02 | EX-017-01, EX-017-02 |
| L-001-005 | 功能安全：PL、SIL 与 ASIL 的区别 | L-003-004 | EX-005-01, EX-005-02 | EX-018-01, EX-018-02 |
| L-001-006 | 测试分层、左移与右移 | L-001-003 | EX-006-01, EX-006-02 | EX-003-01, EX-003-02 |
| L-001-007 | 版本准入、准出与策略落地 | L-001-004 | EX-007-01, EX-007-02 | EX-004-01, EX-004-02 |
| L-002-001 | 测试设计方法工具箱 | L-001-005 | EX-008-01/02/03 | EX-005-01/02/03 |
| L-002-002 | 任务链、长尾场景与故障注入 | L-001-006 | EX-009-01, EX-009-02 | EX-006-01, EX-006-02 |
| L-002-003 | 测试预言与量化指标 | L-001-007 | EX-010-01, EX-010-02 | EX-007-01, EX-007-02 |
| L-002-004 | SIL、HIL 与实时仿真验证 | —（新增） | EX-011-01/02/03 | —（新增） |
| L-002-005 | 实验设计：重复次数、样本量与置信区间 | L-002-006 | EX-012-01, EX-012-02 | EX-013-01, EX-013-02 |
| L-002-006 | Flakiness、基线与趋势分析 | L-002-007 | EX-013-01/02/03 | EX-014-01/02/03 |
| L-003-001 | 缺陷分类、复现与证据链 | L-002-001 | EX-014-01, EX-014-02 | EX-008-01, EX-008-02 |
| L-003-002 | 根因分析：5Why、鱼骨、8D 与 FTA | L-002-002 | EX-015-01, EX-015-02 | EX-009-01, EX-009-02 |
| L-003-003 | 逃逸分析与缺陷预防 | L-002-003 | EX-016-01, EX-016-02 | EX-010-01, EX-010-02 |
| L-003-004 | 覆盖率：需求、代码、场景、风险与接口 | L-002-004 | EX-017-01, EX-017-02 | EX-011-01, EX-011-02 |
| L-003-005 | 回归策略与版本准入 | L-002-005 | EX-018-01, EX-018-02 | EX-012-01, EX-012-02 |
| L-004-001 | 汽车与工业软件标准族 | L-003-002 | EX-019-01, EX-019-02 | EX-016-01, EX-016-02 |
| L-004-002 | 机器人性能评价 | L-003-005 | EX-020-01, EX-020-02 | EX-019-01, EX-019-02 |
| L-004-003 | 市场准入与认证 | L-003-006 | EX-021-01, EX-021-02 | EX-020-01, EX-020-02 |
| L-004-004 | 综合演练 | L-003-007 | EX-022-01/02/03 | EX-021-01/02/03 |

> ⚠️ 迁移会**重排编号**，不是简单加偏移：例如 `EX-003-01` 既是被搬走的旧练习，也是新
> M01 第 3 课要用的号。因此**必须先全部移到临时命名空间，再统一落位**（Task 6 的步骤 2–3），
> 否则会互相覆盖。

**模块**

| 模块 | 标题 | priority | order | 课 |
|---|---|---|---|---|
| M01 | 体系基线：策略、风险、标准与门禁 | P0 | 1 | L-001-001 … L-001-007 |
| M02 | 设计与验证：方法、任务链、预言与实验 | P0 | 2 | L-002-001 … L-002-006 |
| M03 | 缺陷、覆盖与回归 | P0 | 3 | L-003-001 … L-003-005 |
| M04 | 行业标准、认证与综合 | P1 | 4 | L-004-001 … L-004-004 |

**概念**

- 新增 `sil-hil-validation`：title `SIL、HIL 与实时仿真验证`，domain `机器人质量工程`，
  target `L3`，prerequisites `[test-levels-shift, task-chain-fault-injection]`，
  related `[experiment-design, test-oracle-metrics]`，weight `1.0`，
  evidence_criteria：`ec-shv-1`（能为一个验证目标选择合适的 MIL/SIL/HIL/实机层级，L3）、
  `ec-shv-2`（能写出可复现的实时仿真验证方案并解释保真度边界，L3），
  resources `[R-29119-2, R-ASAM-OPENSCENARIO, R-ROS2-SIMULATORS]`。
- `quality-system-synthesis` 的 `prerequisites` 追加 `sil-hil-validation`。
- 其余 21 个概念 ID 与内容不变。

**资源（新增 2 条，均为官方文档）**

```yaml
- id: R-ASAM-OPENSCENARIO
  title: ASAM OpenSCENARIO XML 1.3.0 规范（动态场景描述）
  url: https://openscenario.asam.net/ASAM_OpenSCENARIO_XML/v1.3.0/
  type: standard
  kind: standard
  role: required
  trust: A
  license: ASAM 开放许可（可自由分发）
  last_verified: 2026-11-04
  coverage: [sil-hil-validation]
  why: 写场景库、和供应商/主机厂交换场景文件时，用它对齐语法与语义，避免“同一个场景两份描述”。
- id: R-ROS2-SIMULATORS
  title: ROS 2 官方文档 — Simulators（Gazebo / Webots / MVSim）
  url: https://docs.ros.org/en/humble/Tutorials/Advanced/Simulators/Simulation-Main.html
  type: official-doc
  kind: official_docs
  role: required
  trust: A
  license: 文档 CC-BY-4.0（ROS 2 文档站点）
  last_verified: 2026-11-04
  coverage: [sil-hil-validation]
  why: 搭建 ROS 2 仿真回归环境时，按官方教程选仿真器并接好时钟/传感器桥接。
```

---

### Task 1: 讲评上下文只包含本次提交的题目

**Files:**
- Modify: `src/testbridge/tutor/context.py:50-113`
- Modify: `src/testbridge/tutor/review.py:47-105`
- Test: `tests/test_tutor_review.py`

**Interfaces:**
- Produces: `build_context(pack: ContentPack, lesson_id: str, *, exercise_ids: list[str] | None = None) -> TutorContext`
  - `None`（默认）保持现有行为；`[]` 不输出“练习”段；非空列表只列这些练习（未知 ID 跳过）。
- Consumes: 现有 `TutorContext`、`pack.exercises`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_tutor_review.py` 末尾追加：

```python
OTHER = load_pack(Path(__file__).parents[1] / "tests" / "fixtures" / "packs" / "sample-sensors")


def test_review_context_omits_other_exercises() -> None:
    lesson = OTHER.lesson("L-SYNC-001")
    others = [eid for eid in lesson.manifest.exercises if eid != lesson.manifest.exercises[0]]
    assert others, "fixture must have more than one exercise to prove the rule"
    event = new_event(
        kind="exercise_attempt",
        lesson_id="L-SYNC-001",
        exercise_id=lesson.manifest.exercises[0],
        concept_ids=["timestamp-basics"],
        outcome="correct", score=1.0, max_score=1.0,
        payload={"response": "x"},
    )
    context = build_review_context(OTHER, event)
    for exercise_id in others:
        prompt = OTHER.exercises[exercise_id].prompt
        assert prompt not in context.text


def test_build_context_default_still_lists_all_exercises() -> None:
    from testbridge.tutor.context import build_context

    lesson = OTHER.lesson("L-SYNC-001")
    text = build_context(OTHER, "L-SYNC-001").text
    for exercise_id in lesson.manifest.exercises:
        assert OTHER.exercises[exercise_id].prompt in text


def test_build_context_with_explicit_ids_lists_only_those() -> None:
    from testbridge.tutor.context import build_context

    lesson = OTHER.lesson("L-SYNC-001")
    first, second = lesson.manifest.exercises[0], lesson.manifest.exercises[1]
    text = build_context(OTHER, "L-SYNC-001", exercise_ids=[first]).text
    assert OTHER.exercises[first].prompt in text
    assert OTHER.exercises[second].prompt not in text
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tutor_review.py -q`
Expected: FAIL —— `test_review_context_omits_other_exercises` 与
`test_build_context_with_explicit_ids_lists_only_those` 因参数不存在/题干仍在而失败。

- [ ] **Step 3: 改 `build_context`**

`src/testbridge/tutor/context.py`：签名改为
`def build_context(pack: ContentPack, lesson_id: str, *, exercise_ids: list[str] | None = None) -> TutorContext:`，
并把练习段构建改为：

```python
    selected = manifest.exercises if exercise_ids is None else exercise_ids
    exercise_lines = []
    for exercise_id in selected:
        exercise = pack.exercises.get(exercise_id)
        if exercise is None:
            continue
        options = " ".join(f"{option.id}. {option.text}" for option in exercise.options)
        suffix = f" 选项：{options}" if options else ""
        exercise_lines.append(f"- {exercise.prompt}{suffix}")
```

- [ ] **Step 4: 改 `build_review_context`**

`src/testbridge/tutor/review.py`：`base = build_context(pack, lesson_id, exercise_ids=[]).text`，
并在 `REVIEW_SYSTEM_PROMPT` 规则 4 之后插入两条（保持编号连续，原 4 变 6）：

```python
    "4. 只讲评 <submission> 中的这一道题；不要提及其他练习，"
    "不要说“第 N 题还没做”这类话。\n"
    "5. strengths 与 gaps 只能针对本次作答，不得要求补做其他题。\n"
```

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tutor_review.py -q`
Expected: PASS（全部）。

- [ ] **Step 6: 提交**

```bash
git add src/testbridge/tutor/context.py src/testbridge/tutor/review.py tests/test_tutor_review.py
git commit -m "fix(review): scope review context to the submitted exercise only"
```

---

### Task 2: 旧版本讲评缓存自动失效

**Files:**
- Modify: `src/testbridge/tutor/review_service.py:21,58-78`
- Test: `tests/test_tutor_review_service.py`

**Interfaces:**
- Produces: `ReviewService.PROMPT_VERSION` 由模块常量 `"review/1"` 改为 `"review/2"`；
  缓存命中条件从“存在即返回”变为“存在且 `prompt_version == PROMPT_VERSION`”。
- Consumes: `StoredReview.prompt_version`（已存在）。

- [ ] **Step 1: 写失败测试**

在 `tests/test_tutor_review_service.py` 末尾追加：

```python
def test_stale_prompt_version_regenerates_and_overwrites(tmp_path: Path) -> None:
    client = FakeClient()
    db = tmp_path / "e.db"
    evidence = EvidenceStore(db)
    reviews = ExerciseReviewStore(db)
    service = ReviewService(PACK, evidence, reviews, client, CONFIG)
    attempt = short_answer_attempt(evidence)

    reviews.put(
        evidence_id=attempt.id,
        learner_id="local",
        lesson_id="L-QOS-002",
        exercise_id="EX-QOS-005",
        review=parse_review(REPLY, ["机制", "场景"]),
        model="old-model",
        prompt_version="review/1",
    )

    reply = service.review(attempt.id)

    assert reply.cached is False
    assert client.calls == 1
    assert reviews.get(attempt.id).prompt_version == "review/2"
```

同时把既有断言 `assert reply.evidence_event.payload["prompt_version"] == "review/1"`
改为 `"review/2"`。

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tutor_review_service.py -q`
Expected: FAIL —— 新测试报 `cached is True`（旧缓存被直接返回）。

- [ ] **Step 3: 实现**

`src/testbridge/tutor/review_service.py`：

```python
PROMPT_VERSION = "review/2"
```

```python
        if not refresh:
            stored = self.reviews.get(evidence_id)
            if stored is not None and stored.prompt_version == PROMPT_VERSION:
                return ReviewReply(
                    review=to_review(stored), cached=True, saved=True,
                    evidence_event=None,
                )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tutor_review_service.py tests/test_review_web.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/testbridge/tutor/review_service.py tests/test_tutor_review_service.py
git commit -m "fix(review): regenerate reviews written by an older prompt version"
```

---

### Task 3: 允许提示块使用 `data-tone`

**Files:**
- Modify: `src/testbridge/contract/sanitize.py:20-27`
- Test: `tests/test_sanitize.py`（无此文件则新建 `tests/test_sanitize_tone.py`）

**Interfaces:**
- Produces: `sanitize_fragment` 保留 `data-tone` 于任意允许标签；仍剥除 `style`、`on*`。

- [ ] **Step 1: 写失败测试**

```python
from testbridge.contract.sanitize import find_forbidden_html, sanitize_fragment


def test_data_tone_survives_sanitization() -> None:
    out = sanitize_fragment('<aside class="tb-callout" data-tone="warn">注意</aside>')
    assert 'data-tone="warn"' in out


def test_data_tone_does_not_open_scripting() -> None:
    out = sanitize_fragment(
        '<aside data-tone="warn" style="color:red" onclick="x()">注意</aside>'
    )
    assert "style" not in out
    assert "onclick" not in out
    assert "javascript:" not in sanitize_fragment(
        '<a href="javascript:alert(1)" data-tone="info">x</a>'
    )
    assert find_forbidden_html('<p style="color:red">x</p>')
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sanitize_tone.py -q`
Expected: FAIL —— `data-tone` 被剥除。

- [ ] **Step 3: 实现**

`src/testbridge/contract/sanitize.py` 的 `ALLOWED_ATTRIBUTES["*"]` 集合中加入 `"data-tone"`。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sanitize_tone.py tests/test_contract.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/testbridge/contract/sanitize.py tests/test_sanitize_tone.py
git commit -m "feat(contract): allow data-tone on callouts"
```

---

### Task 4: `lint.lesson_order` 课序与先修一致性门禁

**Files:**
- Modify: `src/testbridge/quality/lint.py`
- Test: `tests/test_quality_lint.py`

**Interfaces:**
- Produces: `LintIssue(code="lint.lesson_order", severity="error", lesson_id=<课ID>, message=<缺失概念与推荐位置>)`，
  由 `evaluate_lint` 在每课检查后汇总。
- 规则：按 `pack.lessons_in_order()` 建立 `concept_id -> 最早出现的课序号`；对课 `i` 的每个概念，
  其每个 `prerequisites` 概念若在包内有课，则必须满足 `index(prereq) <= i`。同课算通过。

- [ ] **Step 1: 写失败测试**

用 `tmp_path` 从 fixture 复制一个包并交换两课，构造“先修在更晚才教”。测试：

```python
def test_out_of_order_prerequisites_are_errors(tmp_path: Path) -> None:
    import shutil, yaml
    from testbridge.content.repository import load_pack
    from testbridge.quality.lint import evaluate_lint

    src = Path(__file__).parents[1] / "tests" / "fixtures" / "packs" / "ros2-qos"
    dst = tmp_path / "p"
    shutil.copytree(src, dst)
    module_yaml = dst / "modules" / "M01" / "module.yaml"
    data = yaml.safe_load(module_yaml.read_text(encoding="utf-8"))
    data["lessons"] = ["L-QOS-003", "L-QOS-001", "L-QOS-002"]
    module_yaml.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    report = evaluate_lint(load_pack(dst))

    codes = [issue.code for issue in report.errors]
    assert "lint.lesson_order" in codes
    offending = [issue for issue in report.errors if issue.code == "lint.lesson_order"]
    assert offending[0].lesson_id == "L-QOS-003"


def test_in_order_packs_pass_the_order_rule() -> None:
    from pathlib import Path as P
    from testbridge.content.repository import load_pack
    from testbridge.quality.lint import evaluate_lint

    root = P(__file__).parents[1] / "tests" / "fixtures" / "packs"
    for name in ("ros2-qos", "sample-sensors"):
        assert not [
            issue for issue in evaluate_lint(load_pack(root / name)).errors
            if issue.code == "lint.lesson_order"
        ]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_quality_lint.py -q -k lesson_order`
Expected: FAIL —— `lint.lesson_order` 不存在。

- [ ] **Step 3: 实现**

`src/testbridge/quality/lint.py` 新增：

```python
def _check_lesson_order(pack: ContentPack) -> list[LintIssue]:
    """Every prerequisite must be taught no later than the lesson using it."""
    lessons = pack.lessons_in_order()
    first_seen: dict[str, int] = {}
    for index, lesson in enumerate(lessons):
        for concept_id in lesson.manifest.concepts:
            first_seen.setdefault(concept_id, index)
    issues: list[LintIssue] = []
    for index, lesson in enumerate(lessons):
        for concept_id in lesson.manifest.concepts:
            concept = pack.concepts.get(concept_id)
            if concept is None:
                continue
            for prereq in concept.prerequisites:
                taught_at = first_seen.get(prereq)
                if taught_at is None or taught_at <= index:
                    continue
                issues.append(LintIssue(
                    "lint.lesson_order",
                    f"{concept_id} 先修 {prereq} 在第 {taught_at + 1} 课，晚于本课第 {index + 1} 课",
                    "error",
                    lesson.manifest.id,
                ))
    return issues
```

并在 `evaluate_lint` 末尾 `issues.extend(_check_lesson_order(pack))` 于 `_check_quiz` 之前。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/Scripts/python.exe -m pytest tests/test_quality_lint.py -q`
Expected: PASS；再跑 `.venv/Scripts/python.exe -m testbridge.cli lint content-packs/robot-quality-system`
Expected: `0 error(s), 0 warning(s)`（旧结构在本次重排前恰好满足先修顺序）。

- [ ] **Step 5: 提交**

```bash
git add src/testbridge/quality/lint.py tests/test_quality_lint.py
git commit -m "feat(quality): require lessons to teach prerequisites before use"
```

---

### Task 5: 概念图与资源新增（SIL/HIL）

**Files:**
- Modify: `content-packs/robot-quality-system/concepts.yaml`
- Modify: `content-packs/robot-quality-system/resources.yaml`

**Interfaces:**
- Produces: 概念 `sil-hil-validation`；资源 `R-ASAM-OPENSCENARIO`、`R-ROS2-SIMULATORS`。

- [ ] **Step 1: 加概念**

在 `concepts.yaml` 中 `test-oracle-metrics` 之后插入 §迁移表“概念”一节给出的条目；
并把 `quality-system-synthesis` 的 `prerequisites` 改为
`[release-gate-regression, functional-safety-pl-sil-asil, market-access-certification, robot-performance-evaluation, sil-hil-validation]`。

- [ ] **Step 2: 加资源**

把 §迁移表给出的两条 YAML 追加到 `resources.yaml` 的 `resources:` 列表末尾。

- [ ] **Step 3: 校验**

Run: `.venv/Scripts/python.exe -m testbridge.cli validate content-packs/robot-quality-system`
Expected: 只有 `sil-hil-validation has no lesson` / `has no exercise` 两条 warning，0 error。

- [ ] **Step 4: 提交**

```bash
git add content-packs/robot-quality-system/concepts.yaml content-packs/robot-quality-system/resources.yaml
git commit -m "content: add SIL/HIL concept and two official simulation sources"
```

---

### Task 6: 课与练习 ID 迁移（先入临时空间，再落位）

**Files:**
- Move/Modify: `content-packs/robot-quality-system/modules/*/lessons/*.html`（21 个）
- Modify: `content-packs/robot-quality-system/exercises.yaml`
- Rewrite: `content-packs/robot-quality-system/modules/M0{1,2,3,4}/module.yaml`

**Interfaces:**
- Consumes: §迁移表。
- Produces: 每课 manifest 的 `id`、`module`、`exercises`；正文 `data-tb-exercise` 挂载点；
  `exercises.yaml` 的 `id` 全部一致。

- [ ] **Step 1: 建 4 个模块目录**

```powershell
cd content-packs/robot-quality-system/modules
New-Item -ItemType Directory -Force M04/lessons | Out-Null
```

（M01–M03 已存在。）

- [ ] **Step 2: 全量改到临时前缀（防撞号）**

写一次性脚本 `tmp_migrate.py`（**不提交**，跑完删除）：对 21 个 `EX-\d{3}-\d{2}` 与
21 个 `L-\d{3}-\d{3}` 的每一处出现（`exercises.yaml`、各 `module.yaml`、各课程 HTML
的 manifest 与挂载点），`re.sub` 替换为 `TMPEX-<旧ID>` / `TMPL-<旧ID>`。
替换后跑一次 `tb validate`（预期大量 error，只要**不是** load.invalid 即说明语法没坏）。

- [ ] **Step 3: 映射到最终 ID 并落位**

同一脚本第二段按 §迁移表把 `TMPL-L-00X-00Y` → 新 `L-…`，`TMPEX-EX-…` → 新 `EX-…`，
并把每个课程的 `"module"` 字段改为新模块号；然后按新 ID 重命名文件名与所在目录

```powershell
# 例：L-003-001 → L-001-003 且从 M03 搬到 M01
Move-Item M03/lessons/L-003-001.html M01/lessons/L-001-003.html
```

完整移动清单就是 §迁移表的新旧课 ID 两列。**L-001-001、L-001-002 原地不动。**

- [ ] **Step 4: 重写 module.yaml**

M01 追加第 3–7 课：
```yaml
lessons: [L-001-001, L-001-002, L-001-003, L-001-004, L-001-005, L-001-006, L-001-007]
concepts: [test-strategy-inputs, risk-grading, standards-map, robot-safety-standards,
           functional-safety-pl-sil-asil, test-levels-shift, entry-exit-criteria]
```
M02：`test-design-techniques, task-chain-fault-injection, test-oracle-metrics,
sil-hil-validation, experiment-design, flakiness-baseline`，课 6 个。
M03：`defect-taxonomy, root-cause-analysis, escape-analysis, coverage-model,
release-gate-regression`，课 5 个。
M04：`automotive-standards, robot-performance-evaluation, market-access-certification,
quality-system-synthesis`，课 4 个，`priority: P1`，`order: 4`。

- [ ] **Step 5: 修正文交叉引用**

`L-001-002.html` 正文有 `<li>L-001-001 的五类策略输入是什么？</li>`（原文如此，是内容
瑕疵）：改成“上一课讲过的五类策略输入是什么？”。其余正文若出现 `EX-…`/`L-…` 字面量，
按新 ID 同步。

- [ ] **Step 6: 校验**

Run: `.venv/Scripts/python.exe -m testbridge.cli validate content-packs/robot-quality-system`
Expected: 仅剩 `sil-hil-validation has no lesson/has no exercise` 两条 warning，0 error。

- [ ] **Step 7: 提交**

```bash
git add -A content-packs/robot-quality-system
git commit -m "content: reorder course into four modules and renumber ids"
```

---

### Task 7: 新增 SIL/HIL 课（L-002-004）

**Files:**
- Create: `content-packs/robot-quality-system/modules/M02/lessons/L-002-004.html`
- Create: `content-packs/robot-quality-system/assets/figures/verification-ladder.svg`
- Modify: `content-packs/robot-quality-system/exercises.yaml`

**Interfaces:**
- Produces: 课 `L-002-004`，概念 `sil-hil-validation`，练习 `EX-011-01/02/03`，
  `objective_map` O1..O3 全覆盖。

- [ ] **Step 1: 写图**

`verification-ladder.svg`：800×320，四层梯形（MIL → SIL → HIL → 实机），左侧标注
“保真度 / 成本 / 迭代速度”三个方向箭头，底部一行说明“越往上越真，越往下越快”。
风格对齐 `assets/figures/test-levels.svg`（`#0f172a` 文字、`#dbeafe/#dcfce7/#fef3c7/#fee2e2`
填充、`role="img"` + `title` + `desc`、`viewBox`）。

- [ ] **Step 2: 写课**

manifest：`id: L-002-004`、`module: M02`、`concepts: [sil-hil-validation]`、
`target_level: L3`、`minutes: 55`、`prerequisites: [test-levels-shift, task-chain-fault-injection]`、
`exercises: [EX-011-01, EX-011-02, EX-011-03]`、
`resources: [R-29119-2, R-ROS2-SIMULATORS, R-ASAM-OPENSCENARIO]`、
`objective_map: {O1: [EX-011-01], O2: [EX-011-02], O3: [EX-011-03]}`。

正文结构（**≥3,500 非空白字符、≥6 个 `<h2>`、≥1 图、≥2 表、≥1 代码块、≥1 提示块**）：

1. `开课前 3 分钟：先回忆`（`<details>` 参考答案）
2. `一、仿真通过、实机失败`（引子场景：园区配送机器人 SIL 回归 2,400 条全绿，实机首周 3 起误停）
3. `二、MIL、SIL、HIL 与实机各回答什么`（`<figure>` + 表：验证层级 / 被测对象 / 时钟来源 /
   典型判据 / 成本 / 能发现什么 / 发现不了什么）
4. `三、时钟与实时预算`（表：仿真步长 1 ms / 4 ms / 10 ms 对控制周期 100 Hz 的余量；
   代码块给出 `ros2 bag` 回放 + 固定步长的配置片段）
5. `四、场景库与可复现性`（OpenSCENARIO 场景参数化；代码块给出一个场景参数块；
   `<aside class="tb-callout" data-tone="warn">` 提示“随机种子不记录 = 不可复现”）
6. `五、传感器与执行器建模的保真度边界`（表：摄像头/激光雷达/IMU/GNSS 的常见建模缺陷
   与对应逃逸风险）
7. `六、实例：行人横穿在 HIL 上怎么验`（数字实例：t=0 行人进入、20 ms 感知、45 ms 规划、
   80 ms 制动指令、HIL 端到端 140 ms、实机 190 ms，余量 60 ms；给出门限判定）
8. `七、失败模式：仿真作弊的六种写法`（列表 + 提示块）
9. `八、检查清单`
10. `小结`

- [ ] **Step 3: 写 3 道练习**

```yaml
- id: EX-011-01
  type: single_choice
  concepts: [sil-hil-validation]
  level: L2
  prompt: 下列哪项是 HIL 相对 SIL 最核心的差别？
  options:
    - {id: a, text: 仿真模型精度更高}
    - {id: b, text: 被测控制器运行在真实硬件与真实时钟上}
    - {id: c, text: 场景数量可以更多}
    - {id: d, text: 不需要现场标定}
  answer: b
  explanation: HIL 把真实控制器接入仿真回路，时钟与 I/O 都是真的；模型精度不是它的定义特征。
  difficulty: 2

- id: EX-011-02
  type: short_answer
  concepts: [sil-hil-validation]
  level: L3
  prompt: 为“转弯中行人横穿”设计一次 HIL 验证，说明验证层级选择理由、时钟与步长、观测指标和通过判据。
  answer: {accepted: [时钟, 步长, 延迟, 判据, 复现], min_hits: 2}
  rubric:
    - {dimension: 层级理由, weight: 0.34, criteria: 说明为什么选 HIL 而不是纯 SIL 或直接实机}
    - {dimension: 时序, weight: 0.33, criteria: 给出步长、时钟来源与端到端延迟预算}
    - {dimension: 判据, weight: 0.33, criteria: 指标可量化、判据可判定、失败可复现}
  hints:
    - {level: 1, text: 先问这次要验证的是算法逻辑还是时序与 I/O。}
    - {level: 2, text: 延迟要拆成感知、规划、执行三段分别量。}
  difficulty: 3

- id: EX-011-03
  type: self_assess
  concepts: [sil-hil-validation]
  level: L3
  prompt: 你当前项目的仿真验证，最不可信的一环是哪里？写出验证它的一次实验。
  rubric:
    - {dimension: 缺口定位, weight: 0.5, criteria: 能指出具体建模或时序上的不可信点}
    - {dimension: 验证方案, weight: 0.5, criteria: 给出的实验能区分“模型对了”和“模型错了”}
  difficulty: 3
```

- [ ] **Step 4: 校验**

```powershell
.venv/Scripts/python.exe -m testbridge.cli validate content-packs/robot-quality-system
.venv/Scripts/python.exe -m testbridge.cli depth content-packs/robot-quality-system
.venv/Scripts/python.exe -m testbridge.cli lint content-packs/robot-quality-system
```
Expected: 三条命令均 0 error；depth 行显示 `L-002-004 L3 chars=≥3500 h2=≥6 tables=≥2 figures=1`。

- [ ] **Step 5: 提交**

```bash
git add content-packs/robot-quality-system/modules/M02/lessons/L-002-004.html \
        content-packs/robot-quality-system/assets/figures/verification-ladder.svg \
        content-packs/robot-quality-system/exercises.yaml
git commit -m "content: add SIL/HIL verification lesson"
```

---

### Task 8: 呈现形式扩写（图 / 代码块 / 提示块）

**Files:**
- Create: `content-packs/robot-quality-system/assets/figures/*.svg`（见下）
- Modify: 各课 HTML

**Interfaces:**
- Consumes: Task 3 的 `data-tone`。
- Produces: 每课 ≥1 提示块；下表列出的课各有图与代码块。

- [ ] **Step 1: 新增 SVG（8 张）**

| 文件 | 用于课 | 内容 |
|---|---|---|
| `standards-map.svg` | L-001-003 | 29119 各部分、ISTQB、ASPICE 的分工与重叠 |
| `safety-standards-map.svg` | L-001-004 | 12100 → 10218/15066/3691-4/13482 的选取树 |
| `pl-sil-asil.svg` | L-001-005 | 三套体系各自的输入、等级轴、验证证据（已存在 `pl-sil-asil.svg`，**复用**） |
| `test-levels.svg` | L-001-006 | **复用**现有文件 |
| `design-methods-map.svg` | L-002-001 | 问题形状 → 方法选择（等价类/边界/判定表/状态迁移/场景/组合） |
| `task-chain.svg` | L-002-002 | **复用**现有文件 |
| `defect-evidence-chain.svg` | L-003-001 | 现象 → 复现条件 → 日志 → 最小化 → 结论 |
| `release-scope.svg` | L-003-005 | 变更 → 影响分析 → 核心/抽样/不测三档 |

- [ ] **Step 2: 给下列课加图（`<figure>` + `figcaption`）**

`L-001-003 standards-map.svg`、`L-001-004 safety-standards-map.svg`、
`L-001-005 pl-sil-asil.svg`、`L-002-001 design-methods-map.svg`、
`L-002-005 experiment-design`（可用 `verification-ladder.svg` 中的分层说明改成独立小图
`sample-size-tradeoff.svg`——或因无合适素材改用表，保持“每课至少一种非纯文字结构”即可）、
`L-003-001 defect-evidence-chain.svg`、`L-003-005 release-scope.svg`、`L-004-003 certification-map.svg`（复用）。

- [ ] **Step 3: 给下列课加代码块**

| 课 | 代码内容 | 语言 |
|---|---|---|
| L-002-002 | 故障注入点配置片段（`yaml`） | yaml |
| L-002-004 | 固定步长仿真启动 + 回放配置（`bash`） | bash |
| L-002-005 | 样本量与置信区间计算（`python`，可复制运行） | python |
| L-002-006 | 从日志统计 flaky 率的脚本（`python`） | python |
| L-003-005 | 按影响面筛选用例的选择表达式（`python`） | python |
| L-004-004 | 证据矩阵的最小 CSV 结构（`csv`） | csv |

统一写法：`<pre data-tb-block="code" data-language="xxx"><code>…</code></pre>`。
**不要**在代码块里写 `<`、`>`、`&` 之外未转义的 HTML 特殊字符会被误解的片段；需要时用
`&lt;` / `&gt;` / `&amp;`。

- [ ] **Step 4: 给全部 22 课加提示块**

每课至少一处，替换正文里现有的“常见误区 / 风险提醒”段落之一：

```html
<aside class="tb-callout" data-tone="warn">
  <p><strong>常见误区：</strong>……</p>
</aside>
```

`data-tone` 取值只用 `info` / `warn` / `error` / `success`（CSS 已定义四种）。

- [ ] **Step 5: 校验**

```powershell
.venv/Scripts/python.exe -m testbridge.cli validate content-packs/robot-quality-system
.venv/Scripts/python.exe -m testbridge.cli depth content-packs/robot-quality-system
.venv/Scripts/python.exe -m testbridge.cli lint content-packs/robot-quality-system
.venv/Scripts/python.exe -m testbridge.cli build content-packs/robot-quality-system --out dist
```
Expected: 前三条 0 error；build 产出 22 个 HTML；抽查 `dist/robot-quality-system/modules/M02/lessons/L-002-004.html` 含 `verification-ladder.svg` 且无 `http://` 外链图片。

- [ ] **Step 6: 提交**

```bash
git add content-packs/robot-quality-system
git commit -m "content: add figures, code blocks and callouts across the course"
```

---

### Task 9: 文档与作者流程

**Files:**
- Modify: `docs/course-briefs/robot-quality-system/MISSION.md`
- Modify: `docs/course-briefs/robot-quality-system/LESSON-BRIEFS.md`
- Modify: `docs/course-briefs/robot-quality-system/RESOURCES.md`
- Modify: `.claude/skills/course-author/SKILL.md`
- Modify: `.claude/skills/course-author/references/authoring-guide.md`
- Modify: `docs/ROADMAP.md`

**Interfaces:**
- Produces: 可复用的“重排流程”章节；与实现一致的 brief 与 roadmap 记录。

- [ ] **Step 1: MISSION 更新**

`Constraints` 改为「4 个模块、22 课、约 1,150 分钟」；`Success looks like` 增一条
“能为一个功能选择 MIL/SIL/HIL/实机层级并写出实时验证方案”。

- [ ] **Step 2: LESSON-BRIEFS 重写**

按新 22 课顺序重排，每课保留 `Tangible win / Primary source / Retrieval / Worked example /
Exercises / Misconception / Figure/table / Minutes`；补 `L-002-004` 一节。
所有 `EX-…` 与 `L-…` 引用改成新 ID。

- [ ] **Step 3: ROADMAP 追加一节**

```markdown
## 2026-11-04 课程体系重排（技能 + 内容）

- 结构：3 模块 21 课 → 4 模块 22 课；标准类课由第 15 课前移到第 3–5 课；
  新增 SIL/HIL 验证课 L-002-004。
- 讲评：上下文只含本次提交的题目；`review/2` 使旧缓存自动失效。
- 呈现：图示 4 → 12 张；6 课新增代码块；22 课各至少 1 个提示块。
- 门禁：`tb lint` 新增 `lint.lesson_order`，课序必须满足先修。
- 与硬边界：`tb/1` 未升版（只加 `data-tone` 白名单与 `build_context` 可选参数）；
  内容仍全在 `content-packs/`，引擎不含学科文本。
```

- [ ] **Step 4: skill 增补“重排流程”**

在 `.claude/skills/course-author/SKILL.md` 的「工作方式」后新增一节：

```markdown
## 按新要求重排课程

1. 写清这次重排的**主线**（一句话），以及“标准/依据”放在前段还是后段。
2. 列出新模块与课序；用 `concepts.yaml` 的 `prerequisites` 逐课核对：先修必须
   在更早或本课出现。违反时 `tb lint` 会报 `lint.lesson_order`。
3. 决定 ID 策略：
   - 有学习证据的 concept/exercise/lesson ID **能不动就不动**；
   - 必须改时，先查 `data/testbridge.db` 的 `evidence` / `review_state` / `mastery_state`，
     在交付说明里写清影响；
   - 练习 ID 用 `EX-<全局课序>-<序号>`，重排时先在临时命名空间里改，再统一落位，
     避免新旧编号互相覆盖。
4. 结构改完先跑 `tb validate`，再 `tb depth` / `tb lint`；lint 不过说明课序与先修不自洽。
5. 更新 `docs/course-briefs/<id>/LESSON-BRIEFS.md` 的课序与 ID 引用。
```

`references/authoring-guide.md` 增补同一条的弱约束版本，并加一节「呈现形式」：
对照型知识用表、过程型知识用图、可执行内容用代码块、误区用提示块。

- [ ] **Step 5: 提交**

```bash
git add docs/course-briefs/robot-quality-system .claude/skills/course-author docs/ROADMAP.md
git commit -m "docs: record the restructure and teach the reorder procedure"
```

---

### Task 10: 全量验证与交付

- [ ] **Step 1: 跑四道门禁**

```powershell
.venv/Scripts/python.exe -m testbridge.cli validate content-packs/robot-quality-system
.venv/Scripts/python.exe -m testbridge.cli depth content-packs/robot-quality-system
.venv/Scripts/python.exe -m testbridge.cli lint content-packs/robot-quality-system
.venv/Scripts/python.exe -m testbridge.cli build content-packs/robot-quality-system --out dist
```
Expected: 均成功；depth 汇总行 `22 lesson(s), 0 error(s)`。

- [ ] **Step 2: 跑全量测试**

```powershell
.venv/Scripts/python.exe -m pytest -q
```
Expected: 除已知基线失败 `test_reading_measure_and_legacy_class_hooks_survive` 外全绿；
若该测试已恢复则全绿。**不修改该测试来让它通过。**

- [ ] **Step 3: 确认学习数据未受影响**

```powershell
.venv/Scripts/python.exe -m testbridge.cli rebuild-state --pack content-packs/robot-quality-system
.venv/Scripts/python.exe -m testbridge.cli readiness --pack content-packs/robot-quality-system
.venv/Scripts/python.exe -m testbridge.cli today --pack content-packs/robot-quality-system
```
Expected: `skipped_exercises` 为空；readiness 仍含 `test-strategy-inputs` 与 `risk-grading`。

- [ ] **Step 4: 提交并汇报**

如实贴出以上命令输出；说明已知基线失败的处理结论。

---

## Self-Review

**Spec coverage** — §3 结构 → Task 5/6/7；§4 讲评 → Task 1/2；§5 呈现 → Task 3/8；§6 可验证性
→ Task 4；§7 验收 → Task 10；§1.1 重排流程 → Task 9。无遗漏。

**Step scan** — 每个代码步骤都给了签名/规则与目标文件；内容步骤给的是结构、字数/元素阈值
与迁移表，而不是整篇课文（课文由实现者写）。SVG 只给内容主题与风格约束，不给路径数据。

**Type consistency** — `build_context(..., exercise_ids=...)` 在 Task 1 定义、Task 1 使用；
`StoredReview.prompt_version` 在 Task 2 使用（已存在）；`LintIssue` 构造签名与现有
`_check_lesson` 一致；概念/练习/课 ID 在迁移表、Task 5、Task 6、Task 7、Task 9 中一致。

**Review Focus** — 5 条各对应测试：Task 1 Step 1 两条上下文测试、Task 2 Step 1 缓存版本
测试、Task 3 Step 1 安全测试、Task 4 Step 1 双向课序测试、Task 6 Step 6 由 `tb validate`
的 `lesson.exercise_unmounted`/`exercise_unlisted` 覆盖挂载同步。

**Proportion** — 计划约 2 倍于 spec，主体是迁移表与门禁规则；课文与 SVG 未写进计划。