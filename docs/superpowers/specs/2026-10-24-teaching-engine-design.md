# TestBridge 教学引擎设计（总图 + 总账 + 分期）

- 状态：Approved，2026-10-24
- 日期：2026-10-24
- 范围：把“教学工程化”与“教学内容”解耦；先建内容契约与运行时，内容后续重写
- 相关文档：[ROADMAP](../../ROADMAP.md)、[CLAUDE.md](../../../CLAUDE.md)

---

## 1. 问题与目标

### 1.1 背景

技术教学系统常见两个问题：

- **内容与引擎耦合**：课程写在页面或目录约定里，内容一改就牵动代码；内容不满意时，工程无法独立演进。
- **学习没有证据**：进度只是一个状态字符串，无法回答“学会了什么、凭什么判断、下一步学什么”。

本项目从零开始，把内容层与教学引擎分离：内容可整包替换，引擎只认契约，学习结论只由证据推导。

### 1.2 目标

把系统拆成两层，并让两层可以独立演进：

1. **内容层**：教什么。概念、课程、练习、资源。可整包替换、可版本化、可由 AI 起草。
2. **教学引擎**：怎么教。加载、校验、渲染、练习、证据、掌握度、复习、推荐。不含任何学科文本。

本期（P1）只做 **内容契约 + 运行时骨架**，不做掌握度算法，也不做 AI 生成。

### 1.3 非目标

- 不做通用 LMS（不处理班级、多租户、权限、成绩单）。
- 不做招聘爬虫或公司情报采集（P4 再议）。
- 不做 3D/仿真编辑器（只留 widget 契约）。
- 不追求一次性覆盖全部学科；先证明契约可替换。

---

## 2. 设计原则（不可破坏）

1. **内容是数据，引擎是解释器。**
   内容包不 import 引擎代码；引擎不写死学科文本。新增模块 = 新增 content pack。

2. **内容状态与学习状态分离。**
   - 内容状态：概念、课程、练习、资源 → 可版本化、可整包替换。
   - 学习状态：作答、证据、掌握度、复习 → 本地、追加式、可重建。

3. **确定性核心，AI 在边缘。**
   判分、掌握度、复习调度不依赖 LLM。LLM 只做讲解、开放题评估、内容起草。换模型不影响学习记录。

4. **证据优先。**
   “学会了”必须能追溯到 Evidence。Mastery 是派生值，不允许手填。

5. **单一事实来源。**
   概念在 `concepts.yaml`，练习在 `exercises.yaml`，资源在 `resources.yaml`；课程只引用 ID。

6. **契约版本化。**
   所有内容文件带 `schema: tb/1`。破坏性变更升 `tb/2`，并提供迁移脚本。

7. **本地优先、可移植。**
   SQLite + 文件；无云依赖；证据可导出 JSONL。

8. **总图优先。**
   每一期只往同一本“能力账本”上加字段；不得另起一套模型。

---

## 3. 总图

```
┌────────────────────────────────────────────────────────────────────┐
│ 应用层                                                             │
│ Learn / Practice / Review / Interview / Company Intel / Dashboard  │
└───────────────────────────────┬────────────────────────────────────┘
                                │
┌───────────────────────────────▼────────────────────────────────────┐
│ 教学引擎（content-agnostic，不含任何学科文本）                      │
│                                                                    │
│  ContentRepository → LessonRuntime → ExerciseRuntime → EvidenceStore│
│         │                  │                │               │       │
│         │                  │                │               ▼       │
│         │                  │                │         MasteryEngine │
│         │                  │                │               │       │
│         │                  │                │         Scheduler(FSRS)│
│         │                  │                │               │       │
│         │                  │                │         Recommender   │
│         │                  │                │               │       │
│         └────────────► ResourceService      │               ▼       │
│                                             │      Capability Ledger│
└───────────────────────────────▲────────────────────────────────────┘
                                │
┌───────────────────────────────┴────────────────────────────────────┐
│ 内容契约层（tb/1）                                                  │
│ manifest schema │ pack loader │ validator │ builder │ sanitizer     │
└───────────────────────────────▲────────────────────────────────────┘
                                │
┌───────────────────────────────┴────────────────────────────────────┐
│ 内容层（可整包替换，不碰引擎代码）                                  │
│ concepts.yaml │ lessons/*.html │ exercises.yaml │ resources.yaml    │
└────────────────────────────────────────────────────────────────────┘
```

**一句话：内容是数据包，引擎是解释器，账本是唯一事实来源。**

---

## 4. 能力账本（总账）

所有阶段共用这一套模型。每一期只新增字段，不另起模型。

### 4.1 对象

| 对象 | 归属 | 含义 | 关键字段 |
|---|---|---|---|
| **Concept** | 内容 | 能力节点 | id, title, domain, target_level, prerequisites, related, evidence_criteria, weight |
| **Lesson** | 内容 | 15–30 分钟学习单元 | id, title, module, concepts, objectives, exercises, resources, minutes |
| **Exercise** | 内容 | 练习/证据来源 | id, type, concepts, level, prompt, options/answer/rubric, hints, difficulty |
| **Resource** | 内容 | 外部材料 | id, title, url, type, trust(A/B/C/D), coverage, license, last_verified, why |
| **Evidence** | 学习者 | 追加式事件，唯一事实 | id, kind, concept_ids, lesson_id, exercise_id, outcome, score, payload, created_at |
| **Mastery** | 派生 | 概念掌握度 | concept_id, estimate, level, confidence, last_evidence_at |
| **ReviewItem** | 派生 | FSRS 卡片 | concept_id, due, stability, difficulty, reps, lapses |
| **Goal/Plan** | 学习者 | 目标岗位、时间预算 | target_role, weekly_hours, concept_weights |
| **Readiness** | 派生 | 总 readiness 分数 | weighted mastery + gate rules |
| **InterviewScore** | 学习者 | 面试 rubric 证据 | question_id, rubric_scores, total, evidence_id |

### 4.2 总分

P2 实现，P1 只留字段与展示位。

```
readiness = Σ(weight_c × mastery_c) / Σ(weight_c)
mastery_c ∈ [0,1]，只由 Evidence 推导
gate：P0 概念未到 L3 时，readiness 上限 0.7
```

“总分”不是孤立数字，必须能下钻到：

```
Readiness → Module → Concept → Evidence → Exercise/Lesson/Resource
```

### 4.3 账本不变量

- 任何 Mastery 变化都必须能指向至少一条 Evidence。
- 任何 Evidence 都必须指向至少一个 Concept；无法归属的作答记为 `unmapped`，不参与掌握度。
- 任何 Lesson 至少关联一个 Concept。
- 任何 Exercise 至少关联一个 Concept。
- Resource 的 `coverage` 必须引用存在的 Concept。
- 内容包可替换；学习记录不随内容包替换而丢失。

---

## 5. 内容契约 `tb/1`

### 5.1 内容包目录

```
content-packs/
  <pack-id>/
    pack.yaml                 # 包元数据、schema 版本、许可证
    concepts.yaml             # 概念图：节点 + 先修边 + 证据标准
    exercises.yaml            # 练习库：按 concept 组织，可跨课复用
    resources.yaml            # 资源库：可信度 + 覆盖概念 + 核验日期
    widgets.yaml              # 交互组件规格：类型 + 参数，由引擎渲染
    modules/
      <module-id>/
        module.yaml           # 模块元数据、课程顺序
        lessons/
          <lesson-id>.html    # HTML 片段 + 内嵌 manifest
    assets/
      figures/                # 图片/SVG
      widgets/                # widget 规格（JSON），由引擎渲染
```

### 5.2 `pack.yaml`

```yaml
schema: tb/1
id: sample-sensors
version: 0.1.0
title: 示例包：传感器时间同步
description: 契约夹具，不是最终教学内容
language: zh-CN
license: CC-BY-4.0
authors: [testbridge]
created: 2026-10-24
fixture: true
```

`modules/<module-id>/module.yaml`：

```yaml
schema: tb/1
id: M01
title: 传感器时间同步
concepts: [sensor-time-sync]
lessons: [L-SYNC-001]
order: 1
```

规则：

- `lessons` 的顺序就是模块内的学习顺序。
- `concepts` / `lessons` 必须引用包内存在的对象。
- `order` 用于模块间排序；重复时按 `id` 稳定排序。

### 5.3 `concepts.yaml`

```yaml
schema: tb/1
concepts:
  - id: sensor-time-sync
    title: 传感器时间同步
    domain: sensors
    target_level: L3
    prerequisites: [timestamp-basics]
    related: [clock-drift]
    weight: 1.0
    evidence_criteria:
      - id: EV-SYNC-EXPLAIN
        description: 能解释时间戳、时钟源、同步误差的来源
        level: L2
      - id: EV-SYNC-DESIGN
        description: 能设计同步误差的测试方法与判定阈值
        level: L3
    resources: [DOC-ROS2-TIME]

  - id: timestamp-basics
    title: 时间戳基础
    domain: sensors
    target_level: L1
    prerequisites: []
    weight: 0.5
    evidence_criteria:
      - id: EV-TS-DEFINE
        description: 能说出时间戳的组成与单位
        level: L1

  - id: clock-drift
    title: 时钟漂移
    domain: sensors
    target_level: L2
    prerequisites: [timestamp-basics]
    weight: 0.5
    evidence_criteria:
      - id: EV-DRIFT-EXPLAIN
        description: 能解释漂移与固定偏移的区别
        level: L2
```

规则：

- `id` 全局唯一，kebab-case；`evidence_criteria[].id` 也全局唯一。
- `prerequisites` / `related` 必须引用存在的 Concept；先修图无环。
- `target_level` ∈ `L1 | L2 | L3 | L4`。
- `evidence_criteria[].level` 不得高于 `target_level`。
- `weight` 是默认权重，Goal 可覆盖。

### 5.4 `exercises.yaml`

```yaml
schema: tb/1
exercises:
  - id: EX-SYNC-001
    type: single_choice
    concepts: [sensor-time-sync]
    level: L2
    prompt: 两个传感器时间戳相差 20ms，最不可能的根因是？
    options:
      - {id: a, text: 时钟源不同}
      - {id: b, text: 传输延迟}
      - {id: c, text: 采样频率不同}
      - {id: d, text: 驱动时间戳打点位置不同}
    answer: c
    explanation: 采样频率影响采样间隔，不直接造成固定时间偏移。
    hints:
      - {level: 1, text: 先区分“偏移”和“间隔”。}
      - {level: 2, text: 固定偏移通常来自时钟或打点位置。}
    difficulty: 2

  - id: EX-SYNC-002
    type: short_answer
    concepts: [sensor-time-sync]
    level: L3
    prompt: 写出一个验证两路传感器时间同步误差的测试方案。
    answer:
      accepted: ["时间戳对齐", "同一事件", "统计偏移", "阈值"]
    rubric:
      - {dimension: 方法, weight: 0.4, criteria: 有可执行的对比方法}
      - {dimension: 判定, weight: 0.4, criteria: 有指标和阈值}
      - {dimension: 失败模式, weight: 0.2, criteria: 提到至少一种异常}
    hints:
      - {level: 1, text: 先找一个可同时被两路传感器观测的事件。}
    difficulty: 3

  - id: EX-SYNC-003
    type: self_assess
    concepts: [sensor-time-sync]
    level: L3
    prompt: 用自己的话解释“时钟漂移”和“固定偏移”的区别。
    rubric:
      - {dimension: 机制, weight: 0.5, criteria: 能区分随时间累积 vs 固定}
      - {dimension: 测试, weight: 0.5, criteria: 能说出对应的检测方法}
```

P1 支持的题型：

| 类型 | 判分 | 证据 |
|---|---|---|
| `single_choice` | 确定性 | outcome + score |
| `multi_choice` | 确定性（全对/部分分） | outcome + score |
| `short_answer` | 关键词/规则匹配 | outcome + score + payload |
| `self_assess` | 学习者自评 + rubric 勾选 | 自评分数 + payload |
| `artifact` | 学习者提交文件/日志/截图 | 附件路径 + 自评 |

`artifact` 的字段（片段，接在 `exercises:` 列表下）：

```yaml
  - id: EX-SYNC-004
    type: artifact
    concepts: [sensor-time-sync]
    level: L3
    prompt: 提交一次同步误差测试的日志和判定结果。
    artifact:
      accept: [log, txt, png, md]
      max_size_mb: 10
    rubric:
      - {dimension: 可复现, weight: 0.4, criteria: 步骤和命令完整}
      - {dimension: 判定, weight: 0.4, criteria: 有指标和阈值}
      - {dimension: 分析, weight: 0.2, criteria: 解释了异常}
```

附件存 `data/artifacts/<evidence-id>/`，Evidence 只存相对路径和自评，不存二进制。

不支持：自由代码执行、LLM 自动评分（P2/P3）。

### 5.5 `resources.yaml`

```yaml
schema: tb/1
resources:
  - id: DOC-ROS2-TIME
    title: ROS 2 Time and Clock
    url: https://docs.ros.org/en/rolling/Concepts/About-Time.html
    type: official-doc
    trust: A
    license: Apache-2.0
    last_verified: 2026-10-24
    coverage: [sensor-time-sync]
    why: 解释 ROS 时间源、仿真时间与时钟类型，是同步测试的一手依据。
```

可信度：

| 级别 | 来源 | 用法 |
|---|---|---|
| A | 官方文档、标准、同行评审论文 | 可作为事实依据 |
| B | 高质量教材、大学课程、维护良好的开源项目 | 主要学习材料，关键结论回溯 A |
| C | 技术博客、演讲、视频 | 补充直觉，需交叉验证 |
| D | 论坛、AI 生成、未署名 | 只作线索 |

### 5.6 课程 HTML + manifest

```html
<script type="application/json" id="tb-manifest">
{
  "schema": "tb/1",
  "id": "L-SYNC-001",
  "title": "时间戳、时钟源与同步误差",
  "module": "M01",
  "concepts": ["sensor-time-sync"],
  "target_level": "L3",
  "minutes": 20,
  "objectives": [
    "能区分固定偏移、漂移、抖动",
    "能设计一个同步误差测试"
  ],
  "prerequisites": ["timestamp-basics"],
  "exercises": ["EX-SYNC-001", "EX-SYNC-002"],
  "resources": ["DOC-ROS2-TIME"]
}
</script>

<article class="tb-lesson">
  <h1>时间戳、时钟源与同步误差</h1>

  <section data-tb-block="prose">
    <p>...</p>
  </section>

  <figure data-tb-block="figure">
    <img src="../../assets/figures/clock-offset.svg" alt="固定偏移与漂移">
    <figcaption>固定偏移 vs 随时间累积的漂移</figcaption>
  </figure>

  <div data-tb-widget="W-SYNC-OFFSET"></div>

  <aside data-tb-block="callout" data-variant="warning">
    <p>不要把采样间隔误判为时间偏移。</p>
  </aside>

  <div data-tb-exercise="EX-SYNC-001"></div>
  <div data-tb-exercise="EX-SYNC-003"></div>

  <section data-tb-block="resources">
    <a data-tb-resource="DOC-ROS2-TIME"></a>
  </section>
</article>
```

块类型（P1）：

| 块 | 写法 | 说明 |
|---|---|---|
| prose | `<section data-tb-block="prose">` | 普通 HTML 正文 |
| figure | `<figure data-tb-block="figure">` | 图片/内联 SVG + 图注 |
| callout | `<aside data-tb-block="callout" data-variant="info\|warning\|tip">` | 提示/警告 |
| code | `<pre data-tb-block="code" data-language="python">` | 代码块 |
| exercise | `<div data-tb-exercise="EX-...">` | 引擎挂载练习 |
| widget | `<div data-tb-widget="W-...">` | 引擎渲染交互组件 |
| resources | `<section data-tb-block="resources">` | 资源列表，引用 `data-tb-resource` |

**manifest 是契约，HTML 是呈现。** 练习定义在 `exercises.yaml`，课程只引用 ID；构建单文件时再内联。

### 5.7 `widgets.yaml`

```yaml
schema: tb/1
widgets:
  - id: W-SYNC-OFFSET
    type: parameter-svg
    title: 固定偏移 vs 漂移
    spec:
      template: assets/widgets/sync-offset.svg
      parameters:
        - {id: offset, label: 固定偏移(ms), min: -50, max: 50, default: 20}
        - {id: drift, label: 漂移(ms/s), min: 0, max: 5, default: 0.5}
    caption: 调整参数，观察两路信号的对齐变化。
```

规则：

- `type` 必须是引擎注册的渲染器；P1 只实现 `parameter-svg`。
- `template` 是包内 SVG，必须存在；参数通过占位符绑定。
- 不允许内容自带 JavaScript。
- 新增 renderer 需要引擎代码 + 测试，不能由内容定义。

### 5.8 校验规则

**Error（阻断发布）：**

- 文件缺少 `schema: tb/1` 或版本不认识。
- ID 重复、格式不合法。
- `prerequisites` / `concepts` / `exercises` / `resources` / `coverage` 引用不存在。
- 先修图有环。
- 练习没有答案或 rubric；rubric 权重和不为 1。
- 课程没有 manifest；manifest 引用的课程概念/练习/资源不存在。
- HTML 含禁止标签或事件属性（见 5.9）。
- widget 引用的规格不存在。

**Warning（提示质量）：**

- 概念没有课程、没有练习。
- 课程没有 objectives、没有练习、没有资源。
- 资源没有 `last_verified`、`license`、`trust`。
- 练习难度与概念目标级别不匹配。
- 外部链接未核验（离线检查时）。

### 5.9 安全与净化

内容可能由 AI 生成，按不可信输入处理。

- **标签白名单**：`article, section, header, footer, h1–h6, p, ul, ol, li, strong, em, code, pre, blockquote, figure, figcaption, img, svg, table, thead, tbody, tr, th, td, a, span, div, aside, details, summary`。
- **属性白名单**：`class, id, data-tb-*, href, src, alt, title, width, height, viewBox, d, fill, stroke, cx, cy, r, x, y, points, transform`。
- **禁止**：`<script>`, `<iframe>`, `<object>`, `<embed>`, `<form>`, `on*` 事件属性, `javascript:` URL, `eval`, 外部脚本。
- **样式**：默认禁止内联 `style`；用共享 class。需要布局时加白名单 class，不放开任意 CSS。
- **外链**：强制 `rel="noopener noreferrer"`，可选 `target="_blank"`。
- **widget**：只允许引擎注册的渲染器；规格是 JSON，不允许内容自带 JS。
- **CSP**：`default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'`。

### 5.10 构建与导出

`tb build` 把内容包构建为：

```
dist/<pack-id>/
  modules/<module-id>/lessons/<lesson-id>.html   # 单文件，可离线打开
  assets/...
  manifest.json
```

保持源目录的相对层级，避免重写内容里的资源路径。

单文件内联：净化后的片段、manifest、练习数据、共享 CSS、运行时 JS、widget 规格。资源外链保留为链接。

独立 HTML 的证据记录：

- 默认写入 `localStorage`。
- 提供“导出证据 JSONL”按钮。
- 不连接服务端；不自动上传。

### 5.11 版本与迁移

- 每个文件必须带 `schema: tb/1`。
- 引擎拒绝未知 major 版本，并给出明确错误。
- P2–P4 只能新增可选字段；语义变更升 `tb/2`。
- `tb migrate <pack> --to tb/2` 在升版本时提供；迁移必须可重复执行、幂等。

---

## 6. 运行时

### 6.1 模块边界

| 模块 | 职责 | 不负责 |
|---|---|---|
| `contract` | Pydantic 模型、schema、校验 | 不做 IO、不写学科文本 |
| `content` | 加载 pack、查询、版本 | 不碰学习状态 |
| `lesson` | 壳、导航、TOC、渲染片段 | 不判分 |
| `exercise` | 挂载、判分、提示、提交 | 不算掌握度 |
| `evidence` | SQLite 追加事件、查询、导出 | 不做解释 |
| `mastery` | 从证据推导掌握度（P2） | 不读 HTML |
| `schedule` | FSRS 队列（P2） | 不选内容 |
| `recommend` | 下一步建议 + 理由（P2） | 不生成内容 |
| `interview` | rubric 评分 → Evidence（P4） | 不渲染课程 |
| `resources` | 可信度、覆盖率、时效 | 不抓网页（P3） |
| `widgets` | 注册渲染器、按 JSON 规格渲染 | 不定义内容语义 |
| `web/cli` | 页面与命令 | 不放业务逻辑 |

### 6.2 数据流

```
pack → validate → repository → lesson render
     → exercise submit → evidence append
     → (P2) mastery → scheduler → recommender → next action
     → (P4) interview score → evidence → mastery
```

### 6.3 课程运行时

- 服务端渲染壳：模块、标题、目标、级别、预计时长、前置、资源、上下课。
- 正文：净化后的 HTML 片段。
- 练习：P1 由服务端把练习表单渲染进占位符；前端 `tb-runtime.js` 只负责提交、提示和反馈。P2 如需离线复用，再抽客户端渲染。
- 提交：`POST /api/evidence`；服务端判分、写库、返回反馈。
- 提示：P1 由服务端把提示渲染进页面，前端逐级展开并记录 `hints_used`；P2 如需防作弊再改为按需返回。
- P1 不做掌握度，只显示“本课已提交 n/m、正确率”。

### 6.4 Evidence Store

SQLite，追加式。建议表结构：

```sql
CREATE TABLE evidence (
  id            TEXT PRIMARY KEY,
  learner_id    TEXT NOT NULL DEFAULT 'local',
  kind          TEXT NOT NULL,          -- exercise_attempt | self_assess | artifact | interview | review | correction
  session_id    TEXT,
  lesson_id     TEXT,
  exercise_id   TEXT,
  concept_ids   TEXT NOT NULL,          -- JSON array
  outcome       TEXT,                   -- correct | incorrect | partial | submitted
  score         REAL,
  max_score     REAL,
  payload       TEXT,                   -- JSON: response, hints_used, duration_ms, rubric
  source        TEXT NOT NULL,          -- web | cli | import | standalone
  created_at    TEXT NOT NULL,
  supersedes    TEXT
);

CREATE INDEX idx_evidence_concept ON evidence(concept_ids);
CREATE INDEX idx_evidence_created ON evidence(created_at);
CREATE INDEX idx_evidence_lesson ON evidence(lesson_id);
```

P1 的 `concept_ids` 先存 JSON 字符串；P2 需要高效按概念聚合时，再加 `evidence_concept` 关联表，不回改 P1 的事件格式。

规则：

- 正常流程只 INSERT；不 UPDATE、不 DELETE。
- 更正用新事件 + `supersedes`，保留历史。
- 导出 JSONL；导入时按 `id` 幂等。
- 数据库文件默认 `data/testbridge.db`；可从空库重建派生状态。

### 6.5 判分

P1 只做确定性判分：

- `single_choice`：选项 ID 相等。
- `multi_choice`：集合相等给满分；部分正确给部分分（可按配置）。
- `short_answer`：规范化（去空白、大小写、标点）后，命中 `accepted` 关键词集合；可选最小命中数。
- `self_assess`：学习者勾选 rubric 维度 + 自评分；不计入“正确率”，只作为证据。
- `artifact`：记录附件路径 + 自评；不自动评分。

**不把 LLM 判分放进核心路径。** P2/P3 可加 `llm_assisted` 评分作为附加证据，但必须标注来源和模型。

### 6.6 独立 HTML 运行时

- 构建时内联练习定义和 widget 规格。
- 判分逻辑用同一份 Python/JS 规则（JS 侧只做展示，最终以导出 JSONL 为准）。
- 证据存 `localStorage`，可导出 JSONL 后由 CLI 导入主库。
- 不执行任意内容脚本；widget 只走注册渲染器。

---

## 7. 应用层（P1 最小）

P1 只做三个页面 + CLI：

| 页面/命令 | 作用 |
|---|---|
| `/` | 包列表、模块列表、继续学习 |
| `/lesson/{id}` | 课程壳 + 正文 + 练习 + 资源 + 上下课 |
| `/progress` | 原始证据列表、按课程/概念聚合的提交数（不做掌握度） |
| `tb validate` | 校验内容包 |
| `tb build` | 构建单文件课程 |
| `tb evidence-export` / `tb evidence-import` | 证据导出/导入 |
| `tb list` | 列出内容包 |

知识地图、追问、公司、题库等页面不在 P1 范围；它们属于 P2–P4。

---

## 8. 分期路线图

> 这一节是防止后续 agent “只看到局部”的总表。任何实现必须先读本节。

| 期 | 目标 | 产出 | 退出标准 | 账本新增 |
|---|---|---|---|---|
| **P0** | 总设计 | 本 spec + ROADMAP + CLAUDE.md | 用户认可，`tb/1` 契约冻结 | 全部对象定义 |
| **P1** | 契约 + 运行时 | schema、validator、loader、renderer、exercise runtime、evidence store、样例包 | 样例包可玩、证据落库、加新包不改代码、测试通过 | Concept/Lesson/Exercise/Resource/Evidence |
| **P2** | 学习闭环 | Mastery、FSRS、Recommender、Dashboard | 能给出“今天学什么 + 为什么”，复习队列可跑 | Mastery/Review/Readiness/Goal |
| **P3** | 内容生产 | 资源检索、AI 起草、质量门禁 | 一个模块端到端产出，带引用并通过校验 | Resource 质量字段、内容版本 |
| **P4** | 应用整合 | 面试、公司情报、求职管理接入 | 面试分数回写证据，弱项驱动计划 | InterviewScore/Goal |

### 8.1 期与期之间的规则

- **P1 冻结 `tb/1`**。P2–P4 只能新增可选字段；破坏性变更升 `tb/2`。
- **P2 之前不实现掌握度算法。**
- **P3 之前不接 AI 内容生成。**
- **P4 之前不把面试塞进学习引擎。**
- **内容编写可以在 P1 契约冻结后并行开始**，不必等 P2/P3。
- 每一期结束必须更新 `docs/ROADMAP.md` 的“当前期”标记和退出标准。

### 8.2 P1 详细范围

**做：**

- `tb/1` Pydantic 模型 + 校验器 + `tb validate` / `tb build` CLI
- content pack 加载器
- 课程壳 + 片段渲染 + 上下课导航
- 练习运行时：单选、多选、简答、自评、产出物
- 提示逐级返回
- Evidence Store：SQLite 追加事件、JSONL 导出/导入
- 一个样例包：1 个模块、3 节课、6 道练习、5 条资源、1 个交互 widget
- 测试：schema、引用完整性、无环、净化、判分、证据写入、渲染快照
- 文档：本 spec、ROADMAP、CLAUDE.md

**不做：**

- BKT / FSRS / 推荐
- AI 内容生成
- 面试/公司情报整合
- 3D/仿真编辑器
- 多用户/权限/多租户

### 8.3 P2 预留

- `mastery` 从 evidence 推导，先规则后 BKT。
- `schedule` 用 `py-fsrs`。
- `recommend` 输出“学什么 + 为什么 + 预计时长”。
- Dashboard：概念图 + 掌握度 + 复习队列 + readiness 总分。
- 面试评分接入 evidence（可提前到 P4）。

### 8.4 P3 预留

- 资源检索：SearXNG/Firecrawl/arXiv/OpenAlex 等。
- AI 起草：按 `tb/1` 生成 pack，必须通过 validator。
- 质量门禁：引用、可信度、练习覆盖、目标级别。
- 内容包演进：`tb migrate` 或批量重新生成。

### 8.5 P4 预留

- 面试引擎：rubric → InterviewScore → Evidence。
- 公司/ JD：概念权重、匹配度。
- 求职管理：投递、复盘。
- 所有应用层只读写账本，不另建状态。

---

## 9. 目录结构（P1 目标）

```
robot/
├─ CLAUDE.md                     # 后续 agent 守则
├─ README.md                     # 项目说明
├─ pyproject.toml
├─ content-packs/
│  └─ sample-sensors/
│     ├─ pack.yaml
│     ├─ concepts.yaml
│     ├─ exercises.yaml
│     ├─ resources.yaml
│     ├─ widgets.yaml
│     ├─ modules/M01/
│     │  ├─ module.yaml
│     │  └─ lessons/L-SYNC-001.html
│     └─ assets/
│        ├─ figures/
│        └─ widgets/
├─ src/testbridge/
│  ├─ contract/                  # 模型 + 校验
│  ├─ content/                   # pack 加载 + 查询
│  ├─ lesson/                    # 渲染 + 壳
│  ├─ exercise/                  # 题型 + 判分 + 提示
│  ├─ evidence/                  # SQLite
│  ├─ resources/                 # 资源服务
│  ├─ widgets/                   # widget 渲染器注册表
│  ├─ cli.py
│  └─ config.py
├─ web/
│  ├─ app.py
│  ├─ templates/
│  └─ static/
│     ├─ tb.css
│     └─ tb-runtime.js
├─ tests/
├─ data/                         # 运行时数据（gitignore）
└─ dist/                         # 构建产物（gitignore）
```

---

## 10. 错误处理

| 场景 | 行为 |
|---|---|
| 内容包校验失败 | `tb validate` 返回非零；列出文件、行号、错误码；不启动服务 |
| 课程 manifest 缺失 | 该课标记为 `invalid`，列表可见但不可打开；不阻塞其他课 |
| 练习引用不存在 | 校验 error；运行时该占位符显示“练习缺失”，不崩溃 |
| 证据写入失败 | 返回 503，前端保留本地草稿；不假装成功 |
| 内容包版本过高 | 拒绝加载，提示升级引擎或迁移内容 |
| 资源链接失效 | 校验 warning；不阻断发布 |
| 独立 HTML 无 localStorage | 降级为内存记录 + 导出按钮 |

---

## 11. 测试策略

| 层 | 测试 |
|---|---|
| contract | schema 校验、ID 唯一、引用完整性、先修无环、rubric 权重 |
| sanitizer | 禁止标签/属性被剥离；合法 HTML 保留；XSS 用例 |
| content | 样例包加载；缺失引用报错；版本不匹配报错 |
| lesson | 渲染快照；manifest 注入；上下课导航 |
| exercise | 各题型判分；提示顺序；部分分；边界输入 |
| evidence | 追加、查询、导出/导入幂等；空库重建 |
| web | FastAPI TestClient：课程页、提交、进度页 |
| build | 单文件 HTML 可离线打开；资源路径正确；证据导出可用 |
| e2e | 打开样例课 → 做题 → 看证据 → 导出 → 导入 |

**完成定义：** `tb validate content-packs/sample-sensors` 通过；`pytest` 全绿；样例课可玩；证据可导出导入；新增一个最小 pack 不需要改代码。

---

## 12. 风险与取舍

| 风险 | 取舍 |
|---|---|
| HTML 内容难校验 | 用 manifest 承载契约，HTML 只做呈现；净化器 + 白名单 |
| AI 生成 HTML 不稳定 | P3 先让 AI 生成 manifest + 受限 HTML；validator 作为门禁 |
| 契约过早复杂 | P1 只支持 5 种题型、1 种 widget；其余留扩展点 |
| 内容包演进 | 版本化 + 迁移脚本 + 向后兼容 |
| 掌握度算法误导 | P2 先规则后 BKT；所有估计可下钻到证据 |
| 独立 HTML 与主库证据分裂 | 统一 JSONL 格式；导入幂等；以主库为准 |
| 内容包安全 | 本地/可信包也走净化；widget 只走注册渲染器 |

---

## 13. 开放问题

P1 不需要回答，记录在此避免遗忘：

- P2 的 BKT 参数如何校准？是否需要按概念类型分模型？
- P3 的资源检索是否需要联网默认开启？离线模式如何降级？
- P4 的面试评分是否允许 LLM 参与？如何标注与复核？
- 多 learner 支持何时引入？当前默认 `learner_id=local`。

---

## 14. 决策记录

### P1 implementation decisions

- 多选部分得分使用 Jaccard 相似度（交集 / 并集）；只有所选集合与答案集合完全相等时才给满分。
- 课程的练习/widget 挂载契约只接受空元素：`<div data-tb-exercise="ID"></div>` 与 `<div data-tb-widget="ID"></div>`，不带任何子内容。
- widget 模板在挂载前先用课程允许列表净化（`sanitize_fragment`），并转义模板内的 `</template`。
- YAML 中未加引号的 `created` / `last_verified` 日期在加载边界统一规范化为 ISO 字符串。
- `tb serve` 在 P1 是仓库内本地能力：运行时把仓库根加入 `sys.path` 再加载 `web.app`，暂不随 wheel 分发。
- 练习 JSON 目前仍暴露 answer 字段；剥离答案字段推迟到 P2，在掌握度/反作弊之前完成。
- P1 的 artifact 练习只记录学习者提供的路径；二进制上传、`accept` / `max_size_mb` 强制校验以及 `data/artifacts/<evidence-id>/` 存储都推迟到 P2。
- P1 独立 HTML 只内嵌课程正文与练习数据，不包含完整的 manifest/objectives 外壳；完整外壳对齐推迟到后续阶段。

| 日期 | 决策 | 理由 |
|---|---|---|
| 2026-10-24 | 内容格式用 HTML 片段 + 内嵌 JSON manifest | 人写/AI 生成都稳定；可交互；可离线；契约可校验 |
| 2026-10-24 | 片段为主，构建导出整页 | 统一壳与运行时；同时保留单文件分发 |
| 2026-10-24 | 先做契约 + 运行时，再做学习闭环 | 内容不满意时，先稳定接口，避免反复推翻 |
| 2026-10-24 | Evidence 用 SQLite，不用 JSON | 证据是追加式事件，需要查询与聚合 |
| 2026-10-24 | 样例包用占位内容 | 只证明契约，不代表最终教学内容 |
