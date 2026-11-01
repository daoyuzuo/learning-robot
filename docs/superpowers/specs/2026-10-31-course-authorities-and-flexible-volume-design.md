# 课程级权威调研与自由课程量设计

- 状态：Implemented，2026-10-31；`pytest` 1250 passed、3 deselected；真实 UDS 烟测
  检索到 ISO 14229-1/2/3/4/6/8 与 ISO 27145-3 的 A/standard 页面，并列出了 DTC/会话细节
  的权威来源缺口；模型提出 3 模块 × 7 课（含 90 分钟课），分模块大纲通过覆盖校验
- 范围：作者层（`studio/`、`web/studio.py`、Studio 页面）；不改 `tb/1`、判分、掌握度、调度
- 上游：[Studio 建课入口](2026-10-27-studio-intake-and-briefs-design.md)、
  [Tutor 联网追问](2026-10-27-tutor-web-grounding-design.md)
- 路线图：[ROADMAP](../../ROADMAP.md)

---

## 1. 目标

在正式排课之前，先找到课程相关的官方/权威资料；课程量由模型基于资料与大纲决定，
不再固定成 1–3 模块 × 1–5 课、总课数 ≤15，也不设单课分钟上限。

```
上传大纲/参考资料 → 课程意图
→ 权威资料调研（Source Map）
→ 课程结构提案（模型决定模块/课数/分钟）
→ 你确认 → 大纲（逐模块生成 + 覆盖校验）
→ 逐课意图 → 逐课调研 → 范围建议 → 写课 → 校验 → 定稿
```

## 2. 非目标

- 不自动抓取任意网页；只通过现有搜索后端检索。
- 不把标准全文下载进仓库；Source Map 只存标题/URL/摘要/信任级别。
- 不设课程量、课数、单课分钟、概念总数的上限；只校验非空、唯一、正数。
- 不自动增加/删除大纲条目；模型可以建议扩层/拆课，但必须等你确认。
- 不改变内容契约、证据、掌握度或调度。

## 3. 决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 权威调研在结构提案之前 | 排课必须基于真实官方/权威来源，而不是模型记忆 |
| D2 | 没有官方/标准 A/B 来源时告警，可填写原因后继续 | 部分主题没有公开全文；硬阻止会让课程无法开始 |
| D3 | 取消模块数、每模块课数、总课数、单课分钟、概念总数上限 | 课程量由模型裁量；只保留正数/唯一/非空校验 |
| D4 | 结构由模型两阶段生成：模块图 → 逐模块课表 | 避免大课程单次 JSON 被截断 |
| D5 | 时间预算只做软目标，显示预计/预算差异 | 不自动砍课，由你决定接受或调整预算 |
| D6 | 大纲条目/顺序/边界仍是强约束，扩层/拆课必须记录映射 | 保持作者控制 |
| D7 | 大纲按模块分块生成后合并 | 大课程不会因单次输出上限失败 |
| D8 | Source Map 的 A/B 来源加入课程资源池 | 课程资源优先使用权威来源 |

## 4. 数据模型（`draft.json`）

```json
{
  "source_map": {
    "queries": ["UDS ISO 14229 ..."],
    "sources": [
      {"title": "...", "url": "...", "trust": "A|B|C",
       "kind": "standard|official_docs|repository|book|other",
       "covers": ["大纲条目"], "why": "..."}
    ],
    "gaps": ["未找到官方来源的条目"],
    "confirmed": false,
    "override_reason": ""
  },
  "structure": {
    "modules": [
      {"id": "M01", "title": "...", "why": "...",
       "lessons": [
         {"id": "L-M01-001", "title": "...", "topics": ["..."],
          "minutes": 45, "depth": "基础|进阶"}
       ]}
    ],
    "estimated_total_minutes": 1800,
    "rationale": "...",
    "mapping": [{"syllabus": "...", "lesson": "..."}],
    "confirmed": false
  },
  "module_lessons": [4, 7, 3]
}
```

- `module_lessons` 是由 `structure` 派生的逐模块课数，供计划/UI/大纲复用。
- 旧草稿没有 `source_map` / `structure`：继续走原有均匀计划路径。
- `module_count` / `lessons_per_module` / `lesson_count` 保留为派生/兼容字段：
  - `module_count = len(modules)`；
  - `lesson_count = sum(module_lessons)`；
  - `lessons_per_module` 仅在均匀结构时填数值，否则可为 `None`。

## 5. 权威资料调研（Source Map）

### 5.1 流程

1. 模型根据大纲条目/主题/参考资料生成 5–8 条权威检索式；不要求它直接给出标准号，
   但鼓励用标准/官方名称（如 UDS → ISO 14229、ISO 15765、AUTOSAR 文档）。
2. 通过现有 `SearchProvider`/`SearchRouter` 逐条检索；按 `search_sources` 分类与信任：
   - 标准：`iso.org`、`iec.ch`、`sae.org`、`ieee.org`、`unece.org` 等；
   - 官方文档、官方仓库、权威书籍；
   - A/B 优先，C 只作补充，D 丢弃。
3. 模型整理 Source Map：标准号/标题、URL、trust、kind、覆盖的大纲条目、why、gaps。
4. 页面展示，用户增删/确认。
5. 确认后进入结构提案；未确认不能提案/生成大纲。

### 5.2 来源门槛

- 至少 1 条 `standard` 或 `official_docs` 的 A/B 来源：正常继续。
- 没有：页面告警，用户填写 `override_reason` 并确认后继续；结构提案提示“官方来源不足”。
- 不静默跳过；`source_map.confirmed` 与 `override_reason` 持久化。

### 5.3 使用

- 结构提案、大纲、写课提示词都带 `<source_map>`。
- Source Map 的 A/B URL 并入课程资源可用池；逐课调研可以补充，但不删除已确认来源。
- 逐课检索可以从 Source Map 的主题/标准号派生查询。

## 6. 课程结构提案

### 6.1 两阶段生成

1. **模块图**：模型输出模块标题、why、每模块课数、预计总分钟、整体 rationale、
   大纲条目到模块/课的 mapping。输出小，适合大课程。
2. **逐模块课表**：对每个模块单独调用模型，输出该模块的课标题、topics、minutes、depth；
   合并为 `structure.modules`。模块数不限，逐模块调用，不会因大 JSON 失败。

### 6.2 校验与确认

- 模块/课标题非空；lesson_count 与 lessons 数量一致；minutes 为正整数；无上限。
- 大纲条目必须出现在 structure 的 lesson/topics/objectives 中；可增加课次/层级，
  但 mapping 必须覆盖原条目，不能丢。
- 时间预算：
  - 显示 `estimated_total_minutes` 与用户预算（weekly_hours × horizon_weeks）的差异；
  - 超出时提示，但不自动压缩；用户可确认、调整预算或让模型重排。
- 用户确认 `structure.confirmed=true` 后才能生成大纲。
- 页面提供结构预览与“让模型调整”输入；可编辑模块/课标题与课数。

## 7. 大纲生成

### 7.1 分块

- 先为每个模块生成概念（`CONCEPT_SYSTEM`），合并成课程概念表；先修关系可引用已有概念。
- 再逐模块生成大纲（`MODULE_OUTLINE_SYSTEM`）：该模块的课标题、objectives、
  research_queries、概念分配；合并为完整 outline JSON。
- 概念总数、模块数、课数均无上限；只校验非空、唯一、先修无环。
- 旧草稿没有 structure 时继续用现有单次大纲生成。

### 7.2 覆盖

- 生成后用 `coverage_report` 对照 syllabus；缺失项阻止调研/写课。
- 结构本身也做一次覆盖检查：大纲条目必须映射到至少一课。
- Source Map 的 gaps 在页面上提示，不阻断（除非用户选择阻断）。

## 8. 接口

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/api/studio/{id}/sources/survey` | 生成检索式、检索、整理 Source Map |
| PUT | `/api/studio/{id}/sources` | 保存/确认 Source Map；可写 override_reason |
| POST | `/api/studio/{id}/structure/propose` | 两阶段生成课程结构 |
| PUT | `/api/studio/{id}/structure` | 保存/确认结构 |
| POST | `/api/studio/{id}/outline` | 按结构分模块生成大纲 + 覆盖校验 |
| 现有 | `/api/studio/{id}/intake*`、`lessons/*`、`batch` | 保持 B 的行为 |

- Source Map / 结构生成是后台任务，带 step 状态与进度；同一 draft 的任务互斥。
- 所有模型输出按不可信输入：长度/数量只做非空与正数校验，展示转义。

## 9. 页面

- 草稿页步骤：0 课程意图 → 1 权威资料 → 2 课程结构 → 3 大纲 → 4 逐课意图 → 5 调研 → 6 写课 → 7 校验 → 8 定稿。
- 权威资料页：检索式、来源分组（标准/官方/参考）、trust、gaps、确认/告警继续。
- 结构页：模块/课列表、预计总时长 vs 预算、mapping、确认；提供“让模型调整”输入。
- 大纲页：分模块生成进度；覆盖缺失阻断。
- 无模型时：可手工维护 Source Map/结构的最小字段；生成按钮禁用。

## 10. 兼容与迁移

- 旧草稿（无 `source_map`/`structure`）继续用原有 `module_count × lessons_per_module`
  与单次大纲生成；不迁移、不重写。
- 新草稿走 Source Map + structure；`module_lessons` 为权威逐模块课数。
- 不改 SQLite 表；Source Map/结构只存 `draft.json`。

## 11. 测试与验收

| 层 | 覆盖 |
|---|---|
| 上限移除 | 大模块数/课数/分钟/概念可通过 store、plan、syllabus、outline |
| Source Map | 查询生成、检索、trust/kind 过滤、无官方来源告警、override 持久化 |
| 结构 | 两阶段合并、逐模块课数、mapping 覆盖、预算差异提示、无上限 |
| 大纲 | 分模块生成合并、覆盖阻断、旧草稿单次路径不回归 |
| Web | 来源调研/确认、结构提案/确认、任务互斥、页面渲染 |
| 回归 | 全量 `pytest`；旧包 `tb validate` / `tb quality` 不回归 |

验收：

- [ ] UDS 示例大纲能检索到 ISO 14229/15765 等标准页面（或明确 gaps），Source Map 可确认。
- [ ] 模型可提出超过 3 模块、每模块超过 5 课、单课超过 60 分钟的结构，系统不拒绝。
- [ ] 无官方来源时告警，填写原因后可继续。
- [ ] 大纲条目未覆盖时不能调研/写课。
- [ ] 旧草稿仍可打开、生成、定稿。

## 12. 不做

- 不下载标准全文、不做 OCR/PDF 解析、不绕过付费墙。
- 不自动删除/改写大纲条目；扩层/拆课只建议，需用户确认。
- 不把 Source Map 写入 `content-packs/` 或 `tb/1`。
- 不保证官方来源一定存在；只保证提示、记录与可追溯。
