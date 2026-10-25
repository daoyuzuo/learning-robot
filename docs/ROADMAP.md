# TestBridge 路线图

> 这是全局路线图。任何实现开始前，先读本文件和
> [教学引擎设计](superpowers/specs/2026-10-24-teaching-engine-design.md)。
>
> **当前期：P2（学习闭环）**
> 状态：实现完成，待验收
>
> P1（内容契约 + 运行时）已完成并合并到 `master`。

---

## 一句话

内容是数据包，引擎是解释器，能力账本是唯一事实来源。

---

## 分期总表

| 期 | 目标 | 产出 | 退出标准 | 账本新增 |
|---|---|---|---|---|
| **P0** | 总设计 | spec + ROADMAP + CLAUDE.md | 用户认可，`tb/1` 冻结 | 全部对象定义 |
| **P1** | 契约 + 运行时 | schema、validator、loader、renderer、exercise runtime、evidence store、样例包 | 样例包可玩、证据落库、加新包不改代码、测试通过 | Concept / Lesson / Exercise / Resource / Evidence |
| **P2** | 学习闭环 | Mastery、FSRS、Recommender、Dashboard | 能给出“今天学什么 + 为什么”，复习队列可跑 | Mastery / Review / Readiness / Goal |
| **P3** | 内容生产 | 资源检索、AI 起草、质量门禁 | 一个模块端到端产出，带引用并通过校验 | Resource 质量字段、内容版本 |
| **P4** | 应用整合 | 面试、公司情报、求职管理接入 | 面试分数回写证据，弱项驱动计划 | InterviewScore / Goal |

---

## 期与期之间的硬规则

1. **P1 冻结 `tb/1`。** P2–P4 只能新增可选字段；破坏性变更必须升 `tb/2` 并提供迁移。
2. **P2 之前不实现掌握度算法。**
3. **P3 之前不接 AI 内容生成。**
4. **P4 之前不把面试塞进学习引擎。**
5. **内容编写可在 P1 契约冻结后并行开始**，不必等 P2/P3。
6. 每期结束必须更新本文件的“当前期”和退出标准。

---

## 不可破坏的边界

- 内容不 import 引擎代码；引擎不写死学科文本。
- 内容状态（可版本化）与学习状态（追加式）分离。
- 确定性核心（判分/掌握度/调度）不依赖 LLM；LLM 只在边缘。
- “学会了”必须能追溯到 Evidence；Mastery 是派生值，不允许手填。
- 概念、练习、资源各自只有一个事实来源；课程只引用 ID。

---

## 能力账本

所有阶段共用一套对象，不另起模型：

```
Concept ──prerequisite──► Concept
   │
   ├── Lesson ──► Exercise ──► Evidence ──► Mastery ──► ReviewItem
   │                                               │
   └── Resource                                    ▼
                                              Readiness
```

总分（P2）：

```
readiness = Σ(weight_c × mastery_c) / Σ(weight_c)
gate：P0 概念未到 L3 时，readiness 上限 0.7
```

下钻路径：

```
Readiness → Module → Concept → Evidence → Exercise / Lesson / Resource
```

---

## P1 范围（已完成）

**做：**

- `tb/1` 模型 + 校验器 + `tb validate` / `tb build`
- content pack 加载器
- 课程壳 + HTML 片段渲染 + 上下课导航
- 练习运行时：单选、多选、简答、自评、产出物
- 提示逐级返回
- Evidence Store：SQLite 追加事件 + JSONL 导出/导入
- 样例包：1 模块、3 课、6 练习、5 资源、1 个交互 widget
- 测试 + 文档

**不做：**

- BKT / FSRS / 推荐
- AI 内容生成
- 面试 / 公司情报
- 3D / 仿真编辑器
- 多用户 / 权限

---

## P1 退出标准

- [x] `tb validate content-packs/sample-sensors` 通过
- [x] `pytest` 全绿
- [x] 样例课能在壳里打开，练习能提交，反馈正确
- [x] Evidence 写入 SQLite，可导出 JSONL，可幂等导入
- [x] `tb build` 产出可离线打开的单文件 HTML
- [x] 新增一个最小 content pack 不需要改引擎代码
- [x] 文档（spec / ROADMAP / CLAUDE.md）与实现一致

---

## P2 范围

**做：**

- Mastery：规则冷启动 + BKT 接管，所有估计可下钻到 Evidence。
- Review：练习级 FSRS 卡与到期队列。
- Readiness：权重化总分 + P0 门控。
- Recommender：每日计划（复习 → 新学 → 补弱），带理由与预计时长。
- Dashboard：`/today`、`/concepts`、`/review`、`/progress`。
- CLI：`rebuild-state`、`goal`、`readiness`、`today`。
- 重建：派生表可由证据重放，增量与全量结果一致。

**不做：** P3/P4（AI 内容生成、资源检索、面试、公司情报）。

---

## P2 退出标准（实现自检）

- [x] `pytest` 全绿，P1 测试无回归
- [x] 掌握度、复习、readiness、今日计划接口可用
- [x] 增量 `record` 与全量 `rebuild-state` 对同一证据序列结果一致
- [x] `tb rebuild-state` 可重复执行，结果幂等
- [x] `/today` 给出带理由、带预计时长的计划
- [x] `/concepts` 显示每个概念的 mastery、level、target、到期数
- [x] `/review` 列出到期卡
- [x] readiness 有总分、模块分、门控原因
- [x] 前端不再返回练习答案；跨课程 evidence 被拒绝
- [x] `tests/test_e2e_p2.py` 覆盖证据 → 重建 → 掌握度 → 复习 → readiness → 计划 → 页面

---

## P2 遗留（P2.1 / 后续）

- 概念页图形化（Mermaid/SVG）；P2 用表格 + 先修关系文本。
- 独立复习播放器；P2 的 `/review` 列表跳转课程页复用已有表单。
- BKT 参数校准（P3 用真实数据）。
- 概念级 FSRS 卡与复习后手动自评。
- Artifact 仍只记录路径；产出物评分（`accept` / `max_size_mb`、`data/artifacts/<evidence-id>/`）顺延。
- CLI 的内容/导入错误仍直接打印 traceback，而不是 `ERROR code: path: message`。
- 旧证据迁移：P1 时期把 self_assess / artifact 行写成 `exercise_attempt` 的记录，在 P2.1 / 真实数据使用前需要规范化。
- P1 工程债中未随 P2 处理的部分：`tb build --lesson` 未知 ID 抛 `KeyError`；单文件 HTML 未内联完整 manifest / objectives / 资源列表；`web/` 与 `web/static` 未进 wheel；`schema_version` 别名；证据导出 100 万条上限、导入非原子、`new_event` 不支持 `supersedes`；CSP 对 `application/json` 内联块的内联报告；首页“继续学习”/内容包列表、提交聚合统计、证据写入失败 503 降级。

---

## P1 遗留（已处理 / 顺延）

- [x] 前端内嵌练习 JSON 已移除（P2 Task 0）。
- [x] 证据 API 校验 `exercise_id` 属于请求的 `lesson_id`（P2 Task 0）。
- [x] web `_script_json` 重复随数据块一并移除。
- Artifact 仍只记录路径；产出物评分顺延，见上方 `P2 遗留`。
- 其余 P1 工程债已合并到上方 P2 遗留。

---

## 后续期摘要

P2 已实现；当前范围、退出标准与遗留以上方 P2 章节为准。

### P3 内容生产

- 资源检索：SearXNG / Firecrawl / arXiv / OpenAlex 等。
- AI 起草：按 `tb/1` 生成内容包，必须通过 validator。
- 质量门禁：引用、可信度、练习覆盖、目标级别。
- 内容包演进：`tb migrate` 或批量重新生成。

### P4 应用整合

- 面试：rubric → InterviewScore → Evidence。
- 公司/JD：概念权重、匹配度。
- 求职管理：投递、复盘。
- 所有应用层只读写账本，不另建状态。

---

## 文档索引

- 总设计：[2026-10-24-teaching-engine-design.md](superpowers/specs/2026-10-24-teaching-engine-design.md)
- Agent 守则：[../CLAUDE.md](../CLAUDE.md)
- 开源项目调研：[research/ai-teaching-open-source.md](research/ai-teaching-open-source.md)
