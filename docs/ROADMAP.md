# TestBridge 路线图

> 这是全局路线图。任何实现开始前，先读本文件和
> [教学引擎设计](superpowers/specs/2026-10-24-teaching-engine-design.md)。
>
> **当前期：P1（内容契约 + 运行时）**
> 状态：实现完成，待验收

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

## P1 范围（当前）

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

- [ ] `tb validate content-packs/sample-sensors` 通过
- [ ] `pytest` 全绿
- [ ] 样例课能在壳里打开，练习能提交，反馈正确
- [ ] Evidence 写入 SQLite，可导出 JSONL，可幂等导入
- [ ] `tb build` 产出可离线打开的单文件 HTML
- [ ] 新增一个最小 content pack 不需要改引擎代码
- [ ] 文档（spec / ROADMAP / CLAUDE.md）与实现一致

---

## 后续期摘要

### P2 学习闭环

- Mastery：先规则，后 BKT；每个估计可下钻到证据。
- Scheduler：`py-fsrs`，按概念/练习生成复习卡。
- Recommender：输出“学什么 + 为什么 + 预计时长”。
- Dashboard：概念图、掌握度、复习队列、readiness 总分。

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
