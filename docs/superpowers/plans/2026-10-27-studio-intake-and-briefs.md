# Studio 大纲/参考资料与逐课意图实施计划（B）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建课入口支持大纲（强约束）与参考资料（弱约束）两类文件，增加课程意图问答、逐课意图和调研后范围建议。

**Architecture:** 文件入口与解析在 `studio/intake.py`；大纲结构与覆盖校验在
`studio/syllabus.py` / `studio/coverage.py`；提示词在 `studio/prompts.py`；草稿字段在
`studio/store.py`；Web 路由与页面在 `web/studio.py` / 模板 / `studio.js`。不改引擎与 `tb/1`。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic v2、Jinja2、原生 JS。

**Spec:** [Studio 大纲/参考资料与逐课意图设计](../specs/2026-10-27-studio-intake-and-briefs-design.md)

## Global Constraints

- 大纲（强约束）与参考资料（弱约束）分开存储、分开进入 `<syllabus>` / `<references>`，不合并。
- 大纲强约束条目、顺序、边界、必须覆盖；不固定每课字数/练习量/深度。
- 调研后的范围建议只提示；接受 minutes/levels 写入 brief，拆课/加层级不自动改大纲。
- 逐课意图优先；未填写按大纲写；批量写课不逐课暂停。
- 文件按不可信输入：后缀/大小/编码限制、HTML 去标签、展示转义。
- 不改 `tb/1`、引擎、判分、掌握度、调度；不新增 SQLite 表。
- 默认 `pytest` 不联网；LLM 用假客户端测试。
- 未经用户明确要求不执行 `git commit`。

---

## 任务

### Task 1：文件入口与存储（`studio/intake.py`）

**接口：**
- `IntakeError(code, message)`
- `IntakeUpload(name, format, raw, text, sha256, chars)`
- `read_upload(filename, data) -> IntakeUpload`
- `store_uploads(store, draft_id, syllabus, references) -> {"syllabus": dict|None, "references": [dict]}`
- `syllabus_text(store, draft_id, meta, limit=12000) -> str`
- `references_text(store, draft_id, meta, limit=12000) -> str`

**验收：** 后缀/大小/编码/NUL/空文件/超过 5 份拒绝；HTML 去 script/style 保留结构；
路径不可逃逸；测试 `tests/test_studio_intake.py` 通过。

### Task 2：大纲结构与覆盖（`studio/syllabus.py`、`studio/coverage.py`）

**接口：**
- `SyllabusError(message)`
- `SyllabusBrief(title, module_count, lessons_per_module, modules, boundaries_in,
  boundaries_out, outcomes, must_cover, mapping, questions, suggestions)`
- `parse_syllabus_json(raw) -> SyllabusBrief`
- `coverage_report(brief, modules, concept_titles) -> list[dict]`
  - 每项 `{"kind","text","module","lesson","covered_by"}`；`covered_by` 为课 ID 或空。
- `normalize(text) -> str`：去空白、标点、大小写，保留中英文数字。

**Syllabus JSON 契约：**

```json
{
  "title": "...",
  "module_count": 2,
  "lessons_per_module": 4,
  "modules": [
    {"title": "...", "lessons": [
      {"title": "...", "topics": ["..."], "from": ["..."]}
    ]}
  ],
  "boundaries_in": [], "boundaries_out": [],
  "outcomes": [], "must_cover": [],
  "mapping": [{"syllabus": "...", "lesson": "..."}],
  "questions": ["..."], "suggestions": ["..."]
}
```

校验：模块 1–3、每模块课 1–5、总课 ≤15 且各模块课数相同；标题非空 ≤120 字；
topics ≤8 条、每条 ≤80 字；mapping ≤30 条；questions ≤3 条；suggestions ≤5 条。
超出/不均时抛 `SyllabusError`，由写课/生成的重试把错误反馈给模型。

**覆盖：** 对每个模块标题、课标题、topics 条目，在生成大纲的模块标题、课标题、
objectives、概念标题中做归一化子串匹配；缺失项 `covered_by=""`。

**验收：** `tests/test_studio_syllabus.py`、`tests/test_studio_coverage.py` 通过。

### Task 3：草稿字段与提示词（`studio/store.py`、`studio/prompts.py`）

- 新草稿增加：
  - `intake = {"syllabus": None, "references": [], "syllabus_brief": None,
    "answers": [], "questions": [], "brief": {...}, "confirmed": False}`
  - `lesson_briefs = {}`
- 旧草稿缺字段时按默认值处理。
- `render_outline_prompt(..., syllabus_text=None, references_text=None, course_brief=None)`：
  增加 `<syllabus>`（强约束）、`<references>`（弱约束）、`<course_brief>`。
- `render_lesson_prompt(..., course_brief=None, lesson_brief=None)`：
  增加 `<course_brief>` 与 `<lesson_brief>`；`<lesson_brief>` 含 intent/must_cover/avoid/
  minutes/levels/scope_notes。
- `SYLLABUS_SYSTEM`、`INTAKE_SYSTEM`、`SCOPE_SYSTEM` 提示词加入 `prompts.py`。
- `PROMPT_VERSION` 升到 `studio/8`。

**验收：** 现有 outline/lesson 提示词测试更新并通过；新块有断言。

### Task 4：Web 建课入口与意图接口（`web/studio.py`）

- `POST /studio` 改 multipart：`draft_id`、`topic?`、`syllabus`、`references`、
  现有级别/检索/高级计划字段。
- 创建后存 intake 元数据，进入草稿页；有大纲时先解析（LLM）再确认。
- `POST /api/studio/{id}/intake`：`action=parse|answer|suggest`，返回
  `syllabus_brief`、`questions`、`brief`；解析成功后更新草稿模块/课数。
- `PUT /api/studio/{id}/intake`：保存/确认 brief；确认前不能生成大纲。
- `POST /api/studio/{id}/outline`：有 syllabus 时做覆盖校验；有缺口返回 409 并列出。
- 研究/写课启动前同样阻断未覆盖项。
- `POST /api/studio/{id}/lessons/{lid}/brief/suggest` 与 `PUT .../brief`；
  `POST .../scope/suggest`（调研后范围建议）。

**验收：** 上传、解析、确认、覆盖阻断、意图保存、范围建议的 Web 测试通过。

### Task 5：页面（`studio_list.html`、`studio_draft.html`、`studio.js`）

- 新建表单：大纲与参考资料两个独立上传控件；其余字段收进「高级选项」。
- 草稿页新增「0 课程意图」：文件摘要、解析按钮、固定问题、建议、brief 编辑、确认。
- 大纲覆盖结果展示：逐条“已覆盖/未覆盖/映射到哪一课”。
- 逐课意图编辑器：intent / must_cover / avoid / minutes / levels；「建议」「保存」。
- 「按调研建议范围」：显示建议，接受 minutes/levels，拆课/主题只提示。
- 无 LLM/文件不可用时，表单仍可手填 brief 并保存。

**验收：** 页面渲染与 JS 接口路径有 Web 测试覆盖；手动/none-LLM 路径可用。

### Task 6：回归与文档

- 旧草稿（无 intake/lesson_briefs）生成、写课、定稿不回归。
- `pytest` 全绿；`ruff` 改动文件通过；`tb validate` / `tb quality` 现有包 0/0、100/100。
- README 增加建课入口说明；ROADMAP 标记 B 完成并记录验证结果。
- 不提交 git，除非用户明确要求。

---

## 执行顺序

Task 1 → 2 → 3 → 4 → 5 → 6。Task 1/2 可派 subagent 独立实现；
Task 3–5 共享 `web/studio.py` 与模板，必须串行并由主会话集成审查。
