# TestBridge P2 学习闭环设计

- 状态：Approved，2026-10-25
- 日期：2026-10-25
- 范围：Mastery（规则 + BKT）、FSRS 复习、Readiness、Recommender、Dashboard
- 上游：[P1 教学引擎设计](2026-10-24-teaching-engine-design.md)
- 路线图：[ROADMAP](../../ROADMAP.md)

---

## 1. 背景与目标

P1 已经具备内容契约、课程渲染、练习判分和追加式证据，但学习记录还只是“证据列表”：没有掌握度、没有复习调度、没有“今天学什么”的建议。

P2 把证据变成学习闭环：

1. **Mastery**：从 Evidence 推导每个概念的掌握度，规则型冷启动，BKT 在有足够练习后接管。
2. **Review**：每个练习一张 FSRS 卡，按到期时间安排复习。
3. **Readiness**：用内容包权重和模块优先级算一个可下钻的总分。
4. **Recommender**：每天输出“复习 → 新学 → 补弱”的计划、理由和预计时长。
5. **Dashboard**：Today、Concepts、Review、Progress 四个页面。

P2 仍然是**内容无关**的：所有学科语义来自 content pack，引擎只认 `Concept / Lesson / Exercise / Evidence`。

## 2. 非目标

P2 不做：

- AI 内容生成、资源检索、JD 采集（P3/P4）。
- 面试评分、公司情报、求职管理（P4）。
- 多用户、权限、多租户。
- BKT 参数校准（先用默认参数，P3 再用真实数据校准）。
- 概念级 FSRS 卡、复习后手动自评（P2 用练习级卡 + 自动评分）。
- 独立复习会话页面（P2 的 `/review` 列表链接到课程页；独立复习播放器放 P2.1）。
- 复杂图布局算法；概念页用表格 + 先修关系展示，图形化渲染放 P2.1。

## 3. 已确认的决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 掌握度模型 | 规则型 + BKT 一起做 | 冷启动稳定，重复练习后更严谨 |
| 规则/BKT 合并 | 规则冷启动 → 3 次练习后 BKT 接管 | 证据少时不用 BKT，证据多时用 BKT |
| FSRS 粒度 | 每个练习一张卡 | 调度具体、可执行 |
| FSRS 评分 | 自动映射 | 不增加用户操作 |
| Readiness 权重 | `concept.weight × module.priority × goal override` | 不依赖 JD 语料，P2 可闭环 |
| 推荐顺序 | 到期复习 → 新学 → 补弱 | 先保住记忆，再推进度，再补短板 |
| 状态存储 | 派生表 + `tb rebuild-state` | Evidence 仍是唯一事实，派生状态可重建 |

## 4. 架构

```
EvidenceStore (append-only)
      │
      ▼
LearningService
  ├─ MasteryEstimator          # RuleBased + BKT + handoff
  ├─ ReviewScheduler           # py-fsrs, exercise-level cards
  ├─ ReadinessCalculator       # weighted mastery + P0 gate
  ├─ Planner                   # review → new → weak, within budget
  └─ Goal                      # target, daily minutes, overrides
      │
      ├── mastery_state        # derived cache
      ├── review_state         # FSRS card state
      └── goal                 # learner settings
      ▲
      └── tb rebuild-state     # replay evidence, idempotent
```

### 4.1 模块边界

| 模块 | 职责 | 不负责 |
|---|---|---|
| `mastery/rule.py` | 规则分、衰减、等级阈值 | 不读 HTML，不排复习 |
| `mastery/bkt.py` | BKT 参数与更新 | 不决定展示文案 |
| `mastery/estimator.py` | 冷启动切换、`MasteryView` | 不写 UI |
| `schedule/fsrs.py` | 评分映射、Card 状态、到期队列 | 不算掌握度 |
| `readiness.py` | 加权总分、P0 门控、原因 | 不做推荐 |
| `recommend/planner.py` | 今日计划、理由、预算 | 不生成内容 |
| `learning/service.py` | 聚合入口，供 Web/CLI 调用 | 不含页面逻辑 |
| `learning/store.py` | 派生表读写、重建 | 不改 evidence |

### 4.2 数据流

```
exercise submit
  → evidence append (已有)
  → LearningService.record(event)
      → mastery_state 更新（规则摘要 + BKT）
      → review_state 更新（FSRS）
  → /today /concepts /progress 读取派生状态

tb rebuild-state
  → 清空 mastery_state / review_state
  → 按 evidence (created_at, id) 重放
  → 重新写入派生状态
```

`evidence` 是唯一事实；`mastery_state` 和 `review_state` 是缓存，可以随时删除重建。`goal` 是学习者配置，不从 evidence 重建。

## 5. 数据模型

同一数据库 `data/testbridge.db`，新增：

```sql
CREATE TABLE mastery_state (
  learner_id TEXT NOT NULL,
  concept_id TEXT NOT NULL,
  rule_score REAL NOT NULL,
  bkt_p REAL NOT NULL,
  exercise_observations INTEGER NOT NULL,
  other_observations INTEGER NOT NULL,
  estimate REAL NOT NULL,
  confidence REAL NOT NULL,
  level TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (learner_id, concept_id)
);

CREATE TABLE review_state (
  learner_id TEXT NOT NULL,
  exercise_id TEXT NOT NULL,
  concept_ids TEXT NOT NULL,          -- JSON array
  due TEXT NOT NULL,                  -- ISO datetime, mirrored for queries
  stability REAL NOT NULL,
  difficulty REAL NOT NULL,
  reps INTEGER NOT NULL,
  lapses INTEGER NOT NULL,
  state TEXT NOT NULL,                -- FSRS state name
  last_review TEXT,
  card_json TEXT NOT NULL,            -- serialized py-fsrs Card
  PRIMARY KEY (learner_id, exercise_id)
);

CREATE TABLE goal (
  learner_id TEXT PRIMARY KEY,
  target_role TEXT NOT NULL DEFAULT '',
  weekly_hours REAL NOT NULL DEFAULT 0,
  daily_minutes INTEGER NOT NULL DEFAULT 45,
  concept_overrides_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL
);
```

规则：

- `learner_id` 默认 `local`；P2 单学习者。
- `concept_ids` 和 `concept_overrides_json` 存 JSON。
- `goal` 没有行时使用默认值：`daily_minutes=45`、`weekly_hours=0`、`overrides={}`。
- `mastery_state.rule_score` 是最近一次计算/重建的快照；读取时 `LearningService` 会按当前时间重算规则分（见 6.1），所以它只是缓存，不是事实。
- `review_state` 的 `card_json` 是 `py-fsrs` Card 的完整序列化（`Card.to_dict()`）；`due`/`stability`/`difficulty`/`state` 是为查询和展示做的镜像字段，重建时按 evidence 顺序重放。
- P2 新增依赖 `fsrs>=6.3,<7`（PyPI 包名是 `fsrs`，仓库是 `open-spaced-repetition/py-fsrs`）。

## 6. Mastery

### 6.1 规则型掌握度

对概念 `c`，收集所有 `concept_ids` 包含 `c` 的 Evidence：

```
age_days = max(0, (now - created_at).total_seconds() / 86400)
decay = 0.5 ** (age_days / 30)
kind_weight:
  exercise_attempt = 1.0
  self_assess      = 0.5
  artifact         = 0.7
share = 1 / max(1, len(event.concept_ids))
w_e = kind_weight * decay * share

rule_score(c) = Σ(w_e * score_e) / Σ(w_e)   # 无证据时为 0
```

`score_e`：

- `exercise_attempt`：`score / max_score`；缺失时按 `correct=1, partial=0.5, incorrect=0`。
- `self_assess` / `artifact`：`score / max_score`；缺失时按 0.5。
- 其它 kind（P4 的 interview 等）P2 不参与。

`share` 防止一个多概念练习把同一份证据重复计入每个概念。

### 6.2 BKT

每个概念独立 BKT，只吃**练习**的二元结果：

- `correct` → 1
- `partial` / `incorrect` → 0
- `self_assess` / `artifact` 不进 BKT

默认参数：

```
p_init  = 0.3
p_learn = 0.15
p_guess = 0.2
p_slip  = 0.1
```

更新：

```
答对：p_obs = p(1-slip) / [p(1-slip) + (1-p)guess]
答错：p_obs = p·slip / [p·slip + (1-p)(1-guess)]
p_next = p_obs + (1 - p_obs) * p_learn
```

### 6.3 冷启动切换

```
n = exercise_observations(c)
if n >= 3: estimate = bkt_p
else:      estimate = rule_score

confidence = min(1, (n + 0.5 * other_observations) / 5)
level = thresholds(estimate)
```

等级阈值：

| estimate | level |
|---|---|
| < 0.25 | `L0`（未入门） |
| 0.25–0.50 | `L1` |
| 0.50–0.75 | `L2` |
| 0.75–0.90 | `L3` |
| ≥ 0.90 | `L4` |

P2 引入 `MasteryLevel = L0 | L1 | L2 | L3 | L4`；`Concept.target_level` 仍使用 P1 的 `L1..L4`。比较时按 `L0 < L1 < L2 < L3 < L4` 排序。

`MasteryView` 同时返回 `rule_score`、`bkt_p`、`estimate`、`confidence`、`level`、`observations`，供页面解释“为什么是这个分”。

### 6.4 证据处理顺序

- 重建按 `created_at` 升序、`id` 升序重放。
- 被 `supersedes` 指向的旧事件跳过；只使用更正事件。
- 未知 `concept_id`（不在当前 pack 中）跳过，并记录 warning，不打断重建。

## 7. FSRS 复习

### 7.1 卡片

- 每个 `exercise_id` 一张卡；第一次练习作答时创建。
- 调度器固定为 `Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False)`：新卡首次评分后直接进入按稳定性计算的间隔，避免默认 60 秒/10 分钟学习步在每日计划里反复出现。
- 自评/产出物不创建卡。
- 卡片 `concept_ids` 来自 exercise 的 concepts。

### 7.2 自动评分

| 作答结果 | FSRS rating |
|---|---|
| `incorrect` | Again |
| `partial` | Hard |
| `correct` + `hints_used > 0` | Hard |
| `correct` + `duration_ms ≤ 20000` | Easy |
| `correct` 其他 | Good |

按表格从上到下匹配，先命中先使用；`duration_ms` 缺失或 0 时按 Good。评分映射是确定性的；原始 `outcome`、`score`、`duration_ms`、`hints_used` 仍保存在 evidence payload 中，P3 可以重新解释。

### 7.3 到期队列

- `due <= now` 的卡进入 `/review`。
- 按 `due` 升序；同 due 按 `exercise_id` 稳定排序。
- 复习完成后仍通过现有 `/api/evidence` 提交，`LearningService.record` 更新 FSRS。
- P2 不做独立复习播放器：`/review` 列出卡片并提供跳转到对应课程页的链接。

### 7.4 重建

- 清空 `review_state`。
- 按 evidence 顺序重放所有 `exercise_attempt`。
- 每个练习第一次出现时创建 Card，之后按 rating 更新。
- 重建必须幂等；同一 evidence 重放两次结果一致。

## 8. Readiness

### 8.1 权重

```
priority_multiplier: P0=1.0, P1=0.7, P2=0.4
weight_c = concept.weight
         * max_priority_multiplier(concept 所属模块)
         * goal_override(c, 默认 1.0)
```

- 一个概念出现在多个模块时，取最高优先级（P0 > P1 > P2）。
- `goal_override` 来自 `goal.concept_overrides_json`，键为 concept_id，值为乘数（默认 1.0）。

### 8.2 总分与门控

```
readiness = Σ(weight_c * mastery_c) / Σ(weight_c)
```

没有概念时 `readiness = 0`。门控：

- 如果任一 P0 概念的 `level < concept.target_level`，则 `readiness = min(readiness, 0.7)`。
- 页面必须显示门控原因，例如：“被 P0 门控：`ros2-qos` 估计 L2，目标 L3”。
- 没有 P0 概念时不做门控。

### 8.3 输出

`ReadinessView`：

- `total`（0–1）
- `by_module`：每个模块的加权分
- `gate_active`：是否触发 P0 门控
- `gate_reasons`：门控原因列表（无门控时为空）
- `breakdown`：概念、权重、mastery、level、target_level

## 9. 今日推荐

### 9.1 输入

- `Goal.daily_minutes`（默认 45）
- 所有概念的 `MasteryView`
- 到期 `review_state`
- 内容包的 module/lesson/concept 图

### 9.2 计划项

每项：

```yaml
type: review | new | weak
concept_ids: [...]
lesson_id: ...        # new/weak（有课程时）
exercise_id: ...      # review；weak 无课程回退到练习时
reason: "..."
estimated_minutes: 5 | lesson.minutes | 10
priority: 0.0-1.0     # 展示值，按原始权重截断
```

`priority` 用于展示和排序稳定性，但候选项排序使用未截断的原始值
`weight × (1 - estimate)`；goal override > 1 时排序仍能区分强弱。

### 9.3 生成顺序

1. **到期复习**
   - 取所有 `due <= now` 的卡，按 due 升序。
   - 最多占 `daily_minutes * 0.5`；每张按 5 分钟估。
   - 理由：“到期复习：<exercise 题干前 30 字>”（`Exercise` 没有 title 字段，用题干代替）。

2. **新学**
   - 候选：没有任何 evidence 的概念；所有先修概念 `mastery >= 0.5`（或等级 >= L2）；当前 `level < target_level`。
   - 排序：`weight_c * (1 - mastery_c)` 降序；同分按 module/lesson 顺序。
   - 取一个 lesson（该 lesson 的 concepts 覆盖候选概念）。
   - 理由：“先修已满足，下一个概念：<concept>”。

3. **补弱**
   - 候选：有 evidence 且 `mastery < 0.5` 的概念。
   - 排序：`weight_c * (1 - mastery_c)` 降序。
   - 取一个 lesson 或一次练习；优先 lesson。概念没有课程、或课程都已用时，
     回退到该概念按 `exercise_id` 排序的第一道练习，`lesson_id` 为空、
     `exercise_id` 有值，按 10 分钟估；两者都没有才跳过。
   - 理由：“掌握度偏低：<concept>（<estimate>）”。

4. 预算截断
   - 按上述顺序累加 `estimated_minutes`，超过 `daily_minutes` 的项跳过。
   - 复习最多占 50%；新学/补弱使用剩余预算。
   - 同一 lesson 被新学和补弱同时选中时只保留一次，用剩余预算补下一个候选。
   - 新学/补弱的 lesson 缺少 `minutes` 时按 20 分钟估。
   - 如果没有任何项：返回 `empty=true`，文案“今天没有必须做的事”，附一个可选深挖建议（最高权重且未达目标的概念）。

### 9.4 确定性

- 不使用 LLM。
- 所有排序都有稳定 tie-break（priority、module order、lesson id、exercise id）。
- 同一输入必须生成同一计划。

## 10. Dashboard 与页面

| 页面 | 内容 | 数据来源 |
|---|---|---|
| `/` | readiness、到期数、今日计划预览、最弱 3 个概念 | LearningService |
| `/today` | 今日计划、每项理由、预计时长、开始链接 | Planner |
| `/concepts` | 概念表 + 先修关系 + 掌握度/等级/目标/到期数；点进看证据 | Mastery + Repository |
| `/review` | 到期卡列表、due、concept、跳转课程页 | ReviewScheduler |
| `/progress` | 原有证据列表 + 掌握度摘要 + readiness + 门控原因 | Evidence + LearningService |

P2 概念页用**表格 + 先修关系文本**；`/today` 和 `/concepts` 都是服务端 Jinja 渲染，不引入前端图库或 CDN。Mermaid/SVG 图形化放 P2.1。

## 11. P1 遗留（P2 Task 0）

### 11.1 移除前端答案数据

- `web/app.py` 不再向 `/lesson/{id}` 注入 `tb-exercise-data`。
- `web/templates/lesson.html` 删除该 `<script>` 块。
- `web/static/tb-runtime.js` 删除 `#tb-exercise-data` 的解析；表单已经由服务端渲染，不需要 exercise 数据。
- 更新 Web 测试，断言页面不再包含 exercise 答案字段。

### 11.2 校验练习归属

- `POST /api/evidence` 在解析 exercise 后，检查 `exercise_id in pack.lessons[lesson_id].manifest.exercises`。
- 不匹配返回 400（`exercise not in lesson`）。
- 增加测试：跨课程 exercise 被拒绝。

## 12. CLI

| 命令 | 作用 |
|---|---|
| `tb rebuild-state --db data/testbridge.db` | 清空并重放派生表 |
| `tb goal show` | 打印当前 Goal |
| `tb goal set --daily-minutes 45 --target-role ... --weekly-hours 10` | 更新 Goal |
| `tb readiness` | 打印总分、模块分、门控原因 |
| `tb today` | 打印今日计划 |

所有命令使用 `--db` 默认 `data/testbridge.db`；`tb readiness` / `tb today` 使用 `--pack` 默认 `content-packs/sample-sensors`（与现有 CLI 一致）。

## 13. 重建与一致性

### 13.1 重建流程

```
1. 读取 Goal（不动）
2. DELETE FROM mastery_state WHERE learner_id=?
3. DELETE FROM review_state WHERE learner_id=?
4. 读取 evidence ORDER BY created_at, id
5. 跳过被 supersedes 的旧事件
6. 顺序重放：
   - 所有事件：规则累加器
   - exercise_attempt：BKT 更新 + FSRS 更新
7. 写入 mastery_state / review_state
```

### 13.2 一致性要求

- `LearningService.record(event)` 增量更新与 `rebuild-state` 全量重放，对同一 evidence 序列必须得到相同的 `estimate/level/rule_score/review_state`（允许时间衰减在两次计算之间的微小差异；测试用固定 `now` 注入）。
- 重建是幂等的：连续执行两次，结果相同。
- 重建失败时保留旧表（事务），不留下半成品。

### 13.3 时间注入

- `LearningService`、`Planner`、规则衰减（`rule_score`）与 `rebuild-state` 使用显式 `now: datetime`（默认 UTC now），测试可固定时间；BKT 重放（`replay_bkt`）按证据顺序确定性重放。
- 规则衰减、到期判断、计划生成都使用同一个 `now`。

## 14. 错误处理

| 场景 | 行为 |
|---|---|
| 未知 concept_id | 跳过并 warning，不打断 |
| 未知 exercise_id | 跳过 FSRS，不打断 |
| 证据中没有练习 | 规则分可用，BKT/FSRS 为空 |
| Goal 缺失 | 使用默认值 |
| `rebuild-state` 失败 | 事务回滚，旧表保留 |
| 时间解析失败 | 该事件跳过并 warning |
| 计划为空 | `empty=true` + 可选建议 |
| P0 门控 | 显示原因，不隐藏总分 |

## 15. 测试

| 层 | 测试 |
|---|---|
| Rule | 衰减、kind 权重、多概念 share、无证据、等级阈值 |
| BKT | 已知序列、答对/答错更新、3 次观测切换 |
| FSRS | 五种 rating 映射、due 队列、重建幂等 |
| Readiness | 权重、模块优先级、P0 门控、无 P0 |
| Planner | 复习优先、先修过滤、预算截断、空计划、稳定排序 |
| Rebuild | 增量 vs 全量（固定 now）、supersedes、未知概念 |
| Web | `/today`、`/concepts`、`/review`、答案不泄漏、跨课程 exercise 400 |
| E2E | 提交 6 道练习 → rebuild → today 有复习/补弱 → readiness 变化 |

验收标准：

- `pytest` 全绿，P1 的 118 个测试不回归。
- `tb rebuild-state` 可重复执行，结果一致。
- `/today` 给出带理由、带预计时长的计划。
- `/concepts` 能看到每个概念的 mastery、level、target、到期数。
- `/review` 列出到期卡。
- readiness 有总分、模块分、门控原因。
- 前端不再返回 exercise 答案；跨课程 evidence 被拒绝。

## 16. 风险与取舍

| 风险 | 取舍 |
|---|---|
| BKT 3 次观测仍不稳 | 显示 confidence；< 3 次继续用规则分 |
| 自动 FSRS 评分有噪声 | 保留原始 outcome/payload；P3 允许自评覆盖 |
| Readiness 长期被 P0 门控 | 页面显示门控原因和差距 |
| 规则分随时间衰减 | 读取时按 `now` 重算；派生表只做缓存 |
| 派生表漂移 | `rebuild-state` + 增量/全量一致性测试 |
| 概念页没有图 | P2 用表格 + 先修文本；图形化 P2.1 |
| 复习页只是列表 | P2 复用课程页表单；独立复习播放器 P2.1 |

## 17. 决策记录

| 日期 | 决策 | 理由 |
|---|---|---|
| 2026-10-25 | 规则 + BKT 同时做 | 冷启动稳定，重复练习后更严谨 |
| 2026-10-25 | 3 次练习后 BKT 接管 | 证据少时 BKT 不可靠 |
| 2026-10-25 | 练习级 FSRS 卡 + 自动评分 | 调度具体，不增加用户操作 |
| 2026-10-25 | 权重来自概念权重 × 模块优先级 | 不依赖 JD 语料 |
| 2026-10-25 | 复习 → 新学 → 补弱 | 先保记忆，再推进度，再补短板 |
| 2026-10-25 | 派生表 + 重建命令 | Evidence 仍是唯一事实 |
| 2026-10-25 | P2 概念页用表格，不做 Mermaid | 避免外部 JS/CDN，P2.1 再做图形化 |
| 2026-10-25 | 复习页复用课程页表单 | 独立播放器放 P2.1 |
