# 课程级权威调研与自由课程量实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> or superpowers:executing-plans.

**Goal:** 在排课前生成权威 Source Map，并让模型基于它自由决定模块、课数、分钟和概念数量。

**Architecture:** Source Map 在 `studio/authorities.py`；两阶段结构在 `studio/structure.py`；
计划/大纲去掉上限并支持逐模块课数；大纲按模块分块生成；Web/UI 增加来源与结构步骤。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic v2、Jinja2、原生 JS。

**Spec:** [课程级权威调研与自由课程量](../specs/2026-10-31-course-authorities-and-flexible-volume-design.md)

## Global Constraints

- 不设模块数、每模块课数、总课数、单课分钟、概念总数上限；只校验正数/非空/唯一。
- 权威调研在结构提案之前；无官方/标准 A/B 来源时告警，可填原因继续。
- 时间预算软目标，不自动砍课。
- 大纲强约束条目、顺序、边界；扩层/拆课必须 mapping 覆盖。
- 结构和大纲分阶段/分模块生成，避免大 JSON 截断。
- 不改 `tb/1`、引擎、SQLite；旧草稿兼容。
- 默认 `pytest` 不联网；LLM/搜索用假客户端测试。
- 未经用户明确要求不执行 `git commit`。

---

## Task 1：移除上限，支持逐模块课数

**Files:** `studio/store.py`、`studio/planning.py`、`studio/syllabus.py`、`studio/outline.py`、相关测试。

**Interfaces:**
- `DraftStore.create(..., module_lessons: list[int] | None = None, ...)`；校验每项 >0、
  `lesson_count == sum`；不再限制模块/课数。
- `draft["module_lessons"]`；`module_count=len`、`lesson_count=sum`；
  均匀时 `lessons_per_module` 填数值，否则 `None`。
- `planning` 去掉 `MAX_TOTAL_LESSONS`/`MAX_MODULES`/`MAX_LESSONS_PER_MODULE` 检查；
  `PlanSuggestion` 增加 `module_lessons: list[int]`；计划 JSON 接受 `module_lessons`。
- `SyllabusBrief` 不再要求各模块课数相同、不再限制模块/课数；
  `module_count=len(modules)`、`lessons_per_module=max(...)`。
- `outline.parse_outline_json` 接受逐模块课数或不再做上限检查；
  新增 `parse_structure_outline_json(raw, structure)` 校验模块/课标题与数量。
- 移除 `MAX_CONCEPTS` 总数上限。

**验收：** 大模块数/课数/分钟/概念可通过；旧均匀调用不回归。

## Task 2：权威资料模块

**Files:** 新建 `studio/authorities.py`、`tests/test_studio_authorities.py`；
`prompts.py` 增加 `SOURCE_QUERY_SYSTEM`/`SOURCE_MAP_SYSTEM` 与渲染函数。

**Interfaces:**
- `SourceEntry(title,url,trust,kind,covers,why)`；`SourceMap(queries,sources,gaps,confirmed,override_reason)`.
- `parse_source_queries_json(raw) -> list[str]`（5–8 条）。
- `filter_sources(hits) -> list[dict]`：`search_sources` 分类/trust，A/B 优先，D 丢弃；
  支持 standard/official_docs/repository/book/other；C 保留为补充。
- `parse_source_map_json(raw) -> SourceMap`；无上限，只校验 URL/标题非空、trust/kind 合法。
- `render_source_queries_prompt(...)`、`render_source_map_prompt(...)`、`<source_map>` 块。

**验收：** UDS 查询生成、trust 排序、D 丢弃、无官方来源 gaps、override 持久化字段。

## Task 3：两阶段结构模块

**Files:** 新建 `studio/structure.py`、`tests/test_studio_structure.py`；
`prompts.py` 增加 `STRUCTURE_SYSTEM`/`MODULE_LESSONS_SYSTEM` 与渲染函数。

**Interfaces:**
- `ModulePlanItem(title, why, lesson_count)`；`Structure(modules, estimated_total_minutes,
  rationale, mapping, confirmed)`.
- `parse_module_map_json(raw) -> list[ModulePlanItem]`；无模块数上限，lesson_count >0。
- `parse_module_lessons_json(raw, module_title, lesson_count) -> list[dict]`；
  课标题/topics/minutes/depth；minutes 正整数，无上限。
- `merge_structure(module_items, per_module_lessons) -> Structure`；
  `structure_to_module_lessons(structure) -> list[int]`。
- `validate_structure(structure, syllabus_brief=None)`：非空/唯一/正数；
  syllabus 条目必须出现在 lessons/topics/objectives。
- 渲染：结构提案输入 `<source_map>`/`<syllabus>`/`<course_brief>`/预算。

**验收：** 2/7/3 等不等课数、>3 模块、>5 课/模块、>60 分钟均可通过；mapping 缺失报错。

## Task 4：Source Map Web 流程

**Files:** `web/studio.py`、`tests/test_studio_sources_web.py`。

- `POST /api/studio/{id}/sources/survey`：后台任务；生成查询 → 搜索 → 过滤 → LLM 整理 →
  写 `draft["source_map"]`；step 状态/进度/互斥。
- `PUT /api/studio/{id}/sources`：保存/确认；无 standard/official_docs A/B 时要求
  `override_reason`；确认后才能结构提案。
- 页面数据：queries/sources/gaps/confirmed/override_reason。
- Source Map A/B URL 加入后续资源可用池接口（供 Task 5 使用）。

## Task 5：结构与分模块大纲 Web 流程

**Files:** `web/studio.py`、`tests/test_studio_structure_web.py`、`tests/test_studio_outline_blocks.py`。

- `POST /api/studio/{id}/structure/propose`：两阶段结构生成；写 `structure`、派生
  `module_lessons`/`module_count`/`lesson_count`；step 进度/互斥。
- `PUT /api/studio/{id}/structure`：保存/确认；确认后允许生成大纲。
- `POST /api/studio/{id}/outline`：有 structure 时按模块生成概念与大纲，合并；
  无 structure 时走旧路径；覆盖校验。
- 结构/大纲任务与现有批量互斥；错误可重试。

## Task 6：页面

**Files:** `web/templates/studio_draft.html`、`studio_list.html`、`web/static/studio.js`。

- 步骤：0 意图 → 1 权威资料 → 2 结构 → 3 大纲 → 4 逐课意图 → 5 调研 → 6 写课 → 7 校验 → 8 定稿。
- 权威资料：检索式、来源分组/trust/gaps、确认/告警继续。
- 结构：模块/课列表、预计时长 vs 预算、mapping、确认/让模型调整。
- 大纲：分模块进度与覆盖缺口。
- 无模型时生成按钮禁用；手工保存仍可用。

## Task 7：回归与文档

- 旧草稿、旧均匀计划、旧大纲路径不回归。
- 全量 `pytest`、`ruff` 改动文件；`tb validate`/`tb quality` 现有包。
- README/ROADMAP 更新；spec 标记 Implemented；不提交 git。
