# TestBridge 路线图

> 这是全局路线图。任何实现开始前，先读本文件和
> [教学引擎设计](superpowers/specs/2026-10-24-teaching-engine-design.md)。
>
> **当前期：P4.3（求职管理）已完成，2026-10-26**
> 状态：分支 `p4.3-job-applications`；P4.2 已完成并合并到 master。
>
> P1、P2、P2.1、内容试点、P2.2、P2.3、P2.4、P3.1、P3.2、P3.3、P3.4、P3.5、P4.1、P4.2、P4.3 均已完成。
> P3.4 把一个包扩展到 1–3 个模块、每模块 1–5 课，支持模块级大纲编辑、包内顺序批量与
> 单课重写。P3.5 增加跨草稿选课重生成、prompt 版本与旧/新快照对比。P4.1 把成套面试模拟
> 接入同一本能力账本：面试建议分经用户确认后写入 `kind=interview` 证据，驱动掌握度与
> `/today` 弱项。P4.2 把 JD 映射为概念权重并给出岗位匹配报告；P4.3 把投递、状态、跟进
> 与复盘做成本地记录。
> 设计见 [P3.5 内容演进](superpowers/specs/2026-10-26-p3.5-content-evolution-design.md)、
> [P4.1 面试闭环](superpowers/specs/2026-10-26-p4.1-interview-loop-design.md)、
> [P4.2 公司/JD 匹配](superpowers/specs/2026-10-26-p4.2-company-jd-design.md) 与
> [P4.3 求职管理](superpowers/specs/2026-10-26-p4.3-job-applications-design.md)。

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

### P2.1 已完成（2026-10-25，分支 `p2.1-cleanup`）

- [x] `/progress?concept=` 过滤时同时显示“本概念 N 条 / 全局 M 条”。
- [x] Planner 复习理由改用题干（`Exercise` 无 title 字段，截断 30 字）。
- [x] Planner 候选项按未截断原始分排序，`PlanItem.priority` 只做展示截断。
- [x] 补弱概念没有课程时回退到该概念的练习（10 分钟）；课程都用完时同样回退。
- [x] 导入证据时非法 JSON / `created_at` / `payload` / `score` 的行跳过并 warning；`rebuild-state` 对脏证据同样跳过，CLI 输出 `WARN`。
- [x] `all_mastery()` 单次扫描证据；`readiness()` / `today_plan()` 可复用传入的 views。
- [x] `review_state` 增加 `(learner_id, due)` 索引。
- [x] Web/测试补强：两概念过滤、到期复习行、补弱回退、无 P0 readiness、数值型 BKT 序列。

### 仍未做

- [x] 独立复习播放器：`/review/session` 一次一张卡，跨课程表单各带 `data-lesson-id`。
- [x] 概念页图形化：`/concepts` 顶部服务端渲染 SVG 先修图。
- [x] Artifact 上传与评分：类型/大小校验、`data/artifacts/<evidence-id>/` 落盘，证据只存路径。
- BKT 参数校准（P3 用真实数据）。
- 概念级 FSRS 卡与复习后手动自评。
- CLI 的内容加载/构建错误仍直接打印 traceback，而不是 `ERROR code: path: message`。
- 旧证据迁移：P1 时期把 self_assess / artifact 行写成 `exercise_attempt` 的记录，在真实数据使用前需要规范化。
- P1 工程债中未随 P2 处理的部分：`tb build --lesson` 未知 ID 抛 `KeyError`；单文件 HTML 未内联完整 manifest / objectives / 资源列表；`web/` 与 `web/static` 未进 wheel；`schema_version` 别名；证据导出 100 万条上限、导入非原子、`new_event` 不支持 `supersedes`；CSP 对 `application/json` 内联块的内联报告；首页“继续学习”/内容包列表、提交聚合统计、证据写入失败 503 降级。

---

## P1 遗留（已处理 / 顺延）

- [x] 前端内嵌练习 JSON 已移除（P2 Task 0）。
- [x] 证据 API 校验 `exercise_id` 属于请求的 `lesson_id`（P2 Task 0）。
- [x] web `_script_json` 重复随数据块一并移除。
- [x] Artifact 上传与评分（P2.4）。
- 其余 P1 工程债已合并到上方 P2 遗留。

---

## P3.1 内容生产工作台（已完成，2026-10-25）

**做：**

- `/studio` 与 `/studio/<id>`：草稿列表、五步工作区。
- 大纲：模型生成、contenteditable 直接编辑、保存时净化。
- 调研：每课可配检索预算，DeepSeek Search/Fetch，档案只读。
- 写课：模型输出 → 课程 HTML / 练习 / 资源，YAML 合并。
- 门禁：离线 `validate` + 资源可达性；定稿只拷贝内容文件。
- 后台线程 + `draft.json` 状态轮询；重启把 `running` 记为 `failed`。
- 默认测试全假、不联网；`TESTBRIDGE_LIVE=1` 才跑真实调用。

**不做：** 批量重生成、`tb migrate`、多模块包、多人协作、草稿版本历史。

**退出标准：**

- [x] 全程页面完成：新建 → 编辑大纲 → 调研 → 写课 → 校验 → 定稿
- [x] 定稿后的包通过 `tb validate`，可在 `/lesson/<id>` 打开
- [x] `studio/` 不 import mastery / schedule / learning / evidence
- [x] 密钥只从环境变量读取，不落盘、不回显
- [x] 默认 `pytest` 全绿且不联网；P2 的测试无回归
- [x] `drafts/` 已 gitignore

---

## P3.2 质量门禁（已完成，2026-10-25）

- [x] `src/testbridge/quality/`：报告、结构规则、溯源规则、组合评估
- [x] `tb quality <pack>`：退出码 0/1/2、`--json`、自动读取草稿
- [x] Studio 校验页显示质量分、分项与问题
- [x] 硬错误阻断定稿；`force` / `skip_verify` 不绕过
- [x] 写课提示词包含质量约束
- [x] P3.2 前 369 个测试无回归；P3.2 完成时全量 421 passed（2 个 live 默认取消选择）

### P3.2 遗留（合并后记录）

- **溯源信任缺口（P3.3 决定收紧）**：资源 URL 必须出现在至少一条 A/B 命中里；
  只出现在 C/D 命中时新增 `quality.resource_untrusted_source` 硬错误。实现与
  验收见 P3.3 spec §9。
- 重新生成课程后，页面继续显示上一次校验分数，直到再次校验；定稿门禁每次
  重算，不影响安全。
- `tb quality --json` 遇结构无效包仍打印人类可读错误（非 JSON）；显式空
  `--research-dir ""` 的文案显示 `None`。
- `evaluate_provenance(include_metrics=...)` 只控制 trust/metadata 两项指标，
  traceable/dossiers/queries 不受控；当前无调用者触发。
- 依赖边界测试只匹配 `testbridge.<module>` 字符串，不覆盖相对 import。
- `test_force_does_not_bypass_quality` 在两个测试文件中重名（行为各自独立）。

---

## P3.3 检索后端（已完成，2026-10-25）

**范围：**

- `OpenAlexSearch`：`/works` 检索，摘要还原，DOI/landing page/OA URL 映射。
- `SearchRouter`：关键词 + concept.domain 自动路由；auto 逐查询回退；手动
  `deepseek` / `openalex` 不回退。
- 草稿级 `search_backend`（`auto` / `deepseek` / `openalex`）与新建表单。
- OpenAlex authority：评审 A、预印本 B、其他 C、撤稿 D。
- 调研档案与页面记录实际使用的 backend。
- 溯源信任收紧：C/D-only 来源阻断定稿。

**不做：** SearXNG / Firecrawl / arXiv 适配器、网页抓取、结果缓存、跨后端扇出。

**退出标准（实测，2026-10-25）：**

- [x] 学术主题自动走 OpenAlex，文档主题自动走 DeepSeek；auto 无命中或失败时回退
- [x] 手动选择严格生效，不静默回退
- [x] C/D-only 来源被质量门禁阻断；A/B 不受影响
- [x] 旧草稿缺字段按 auto（代码默认）
- [x] 默认 `pytest` 全绿且离线：458 passed，3 deselected（live）
- [x] 两个现有包 `tb validate` 仍 0/0（ros2-qos、sample-sensors）
- [x] `tb quality content-packs/sample-sensors` 100/100，退出码 0
- [x] `TESTBRIDGE_LIVE=1 pytest -m live`：3 passed（含 OpenAlex 真实检索）

---

## P3.4 多模块与批量（已完成，2026-10-26）

**范围：**

- 一个包 1–3 个模块，每模块 1–5 课；全局概念 + 模块子集 + 课概念。
- 大纲 HTML 可编辑模块标题/概念/课程归属；保存重写 `module.yaml`。
- 包内顺序批量：只跑 pending/failed，逐课进度与失败隔离。
- 单课重写替换旧练习/资源，不产生重复 ID。
- 旧草稿与旧扁平 outline 兼容。

**不做：** 跨主题批量建包、并行批量、取消运行中的批量、自动发布。

**退出标准（实测，2026-10-26）：**

- [x] 2 模块 × 2 课生成 → 校验 → 定稿，`tb validate` 0/0
      （`test_multi_module_batch_end_to_end`：4 课全部 done，定稿包 `validate_pack().errors == []`）
- [x] `module.yaml` concepts/lessons/order 正确
      （M01 `concepts=["c-one"]`、`lessons=["L-1","L-2"]`、`order=1`；M02 `lessons=["L-3","L-4"]`、`order=2`）
- [x] 大纲编辑后 module.yaml 同步（`test_save_outline_rewrites_module_yaml_and_rekeys`）
- [x] 批量只跑待办；失败继续；进度可见
      （`test_batch_research_runs_every_pending_lesson`、`test_batch_returns_empty_when_nothing_is_pending`、
      `test_batch_lessons_continues_after_failure`、`test_draft_page_shows_batch_and_rewrite_controls`）
- [x] 单课重写替换旧输出（`test_single_lesson_rewrite_uses_replace`：旧 `EX-1-*` 释放，练习数不变且 ID 唯一）
- [x] 旧草稿可继续使用（`tests/test_studio_multi_legacy.py` 3 个测试：旧 store 字段、扁平 outline 保存、缺字段跑大纲）
- [x] 批量与单课互斥返回 409（`test_batch_rejected_while_single_job_runs`、`test_single_job_rejected_while_batch_runs`）
- [x] 默认 `pytest` 全绿，现有 458 个测试无回归（518 passed，3 deselected）

**验证命令（2026-10-26）：**

```text
$ .venv/Scripts/python -m pytest -q
518 passed, 3 deselected

$ .venv/Scripts/python -m testbridge.cli validate content-packs/ros2-qos
0 error(s), 0 warning(s)        # exit 0

$ .venv/Scripts/python -m testbridge.cli validate content-packs/sample-sensors
0 error(s), 0 warning(s)        # exit 0

$ .venv/Scripts/python -m testbridge.cli quality content-packs/sample-sensors
quality: 100/100                # exit 0
```

---

## P3.5 内容演进（已完成，2026-10-26）

**范围：**

- `/studio/evolution`：跨草稿选课，按草稿分组、组内按大纲顺序串行重生成。
- prompt 版本：当前 `studio/2`，旧草稿 `studio/1`；每课记录实际版本与写入时间。
- 每课重写前快照旧 HTML/练习/资源到 `drafts/<id>/history/<lesson_id>/`；重写后记录
  练习数/题型/级别/资源数/trust/HTML/版本变化。结果页展示练习/资源数与质量分 delta，
  级别与 trust 在历史页对比。
- 每个草稿记录整包质量分前后 delta；报告写 `history/evolution-<时间戳>.json`。
- 历史页 `/studio/<id>/history/<lesson_id>` 展示“最近一次与当前内容不同的快照 vs 当前”摘要。
- 单课失败继续；草稿忙整组失败；进化任务与批量/单课互斥。

**不做：** `tb migrate`、完整行级 diff、快照回滚、重生成已发布 content-packs、取消运行中任务。

**退出标准（实测，2026-10-26）：**

- [x] 跨两个草稿勾选 3 课，运行后每课有旧/新快照与 delta
      （手工验收：`demo` L-1/L-2 + `other` L-2；`started=3`、`status=done`、
      `done/total=3/3`；每课各 1 份 `snapshot_before` / `snapshot_after`，
      `prompt_version` 由 `studio/1` 变 `studio/2`）
- [x] 每个草稿显示质量分前后；历史页可下钻
      （`test_evolution_api_rewrites_targets_across_drafts`：两草稿 `quality_before/after` 非空；
      `test_history_page_shows_snapshot_and_current`：左侧 `studio/1`、右侧 `studio/2`）
- [x] 单课失败不影响其它
      （`test_evolution_continues_after_one_lesson_fails`、
      `test_evolution_does_not_rewrite_when_before_snapshot_fails`）
- [x] 新写课程记录 `studio/2`，旧课程仍显示 `studio/1`
      （`test_evolution_records_prompt_version_and_batch_step`、
      `test_evolution_page_lists_drafts_and_lessons`）
- [x] 进化任务运行中第二个任务 409；同草稿批量/单课互斥
      （`test_evolution_returns_conflict_while_running`；`JobRunner` 既有互斥测试不回归）
- [x] 默认 `pytest` 全绿；P3.4 的 518 个测试无回归，P3.5 完成时全量 564 passed、3 deselected

---

## P4.1 面试闭环（已完成，2026-10-26）

**范围：**

- 题库先落 `interview-banks/<pack-id>.yaml`，目标形态是包内 `interviews.yaml`，两者同构。
- 成套模拟：默认 3 题、可选 5 题，弱项优先抽题，可手动覆盖概念。
- 作答 → LLM 逐维建议评分 → 用户审阅改分 → 确认后写 `kind=interview` 证据。
- 会话可暂停、恢复、放弃；答案提交即落库，确认幂等。
- 无 LLM 时降级为手动 rubric 评分。
- 引擎加法：面试权重 0.6、独立计数、不进 BKT；planner 弱项包含面试失分。

**不做：** 行为题、系统设计题、多轮追问、语音、强制计时、JD 匹配（P4.2）、
投递复盘（P4.3）、把 `interviews.yaml` 纳入 `tb/1` 校验（P4.1b）。

**退出标准（实测，2026-10-26）：**

- [x] 3 题模拟可从 `/interview` 开始、暂停、恢复、完成并生成汇总
      （`test_three_question_flow_reaches_today`、`test_session_resumes_after_app_restart`、`test_confirm_writes_evidence_and_summary`）
- [x] 每题确认后写面试证据，重复确认不重复写
      （`test_confirm_writes_evidence_and_summary`：重复确认返回同一 `evidence_id`）
- [x] 能下钻到面试证据与原始回答
      （`test_progress_shows_interview_evidence` + `test_confirm_writes_evidence_and_summary`：
      类型列链接会话汇总，汇总页“回答”列展示原始回答）
- [x] 面试失分概念进入 `/today` 弱项
      （`test_three_question_flow_reaches_today`：`/today` 出现“面试失分”）
- [x] 未配置 LLM 时可手动打分完成流程
      （`test_manual_scoring_flow_writes_evidence`：`mode=manual`，确认后写证据）
- [x] `pytest` 全绿，P3.4 / P3.5 无回归（合并后 662 passed，3 deselected；含最终评审修复波次）
- [x] 两个现有包 `tb validate` 仍 0/0

**设计：** [P4.1 面试闭环](superpowers/specs/2026-10-26-p4.1-interview-loop-design.md)

**验证命令（2026-10-26）：**

```text
$ .venv/Scripts/python -m pytest -q
662 passed, 3 deselected in 43.29s

$ .venv/Scripts/python -m testbridge.cli validate content-packs/ros2-qos
0 error(s), 0 warning(s)        # exit 0

$ .venv/Scripts/python -m testbridge.cli validate content-packs/sample-sensors
0 error(s), 0 warning(s)        # exit 0

$ .venv/Scripts/python -m testbridge.cli quality content-packs/sample-sensors
quality: 100/100             # exit 0
```

---

## P4.2 公司/JD 匹配（已完成，2026-10-26）

**范围：**

- 单目标 JD：粘贴文本 → LLM 抽取要求 → 映射到包内概念 + 重要度 → 用户确认权重。
- 只加分：`must=1.6`、`high=1.3`、`normal=1.0`；未提及概念保持 1.0；确认时整体替换
  `Goal.concept_overrides`，只存 `> 1.0` 的权重。
- 匹配报告：JD 加权 readiness、按模块分、未达标概念、最该补的 3 个、内容缺口。
- 无 LLM 时手动权重表；JD 原文与解析结果存 `target_jd` 一行。
- 引擎零改动：复用 `concept_weights` 与 `calculate_readiness`。

**不做：** JD URL 抓取、多 JD 对比、简历匹配、投递记录（P4.3）、按 JD 要求给所需等级。

**退出标准（实测，2026-10-26）：**

- [x] 粘贴 JD → 解析 → 审核 → 确认，`Goal.concept_overrides` 与 `target_role` 更新
      （`test_confirm_writes_goal_and_target`：`concept_overrides == {"sensor-time-sync": 1.6, "clock-drift": 1.3}`、
      `target_role == "具身智能测试工程师"`）
- [x] `/target` 展示 JD 加权 readiness、按模块分、未达标概念、top 3、内容缺口
      （`test_confirmed_target_shows_report`、`test_end_to_end_target_weights_reach_planner_inputs`：
      页面含“岗位匹配度”“未达标概念”）
- [x] `/today` 按新权重排序；未提及概念仍可被安排（planner 复用 `concept_weights`，
      目标权重写入 `Goal.concept_overrides` 后即进入计划打分的权重项，未提及概念保持 1.0；
      `test_end_to_end_target_weights_reach_planner_inputs` 断言权重生效：
      `sensor-time-sync` 1.6、`clock-drift` 0.65、`timestamp-basics` 0.5）
- [x] 无 LLM 时可手动填权重并完成确认
      （`test_manual_mode_without_usable_llm`：解析失败显示“自动解析失败”，手动提交 303）
- [x] 未知概念/非法权重被拒绝（400），JD 原文与理由正确转义
      （`test_confirm_rejects_out_of_range_weight`、`test_confirm_rejects_unknown_concept_in_requirements`、
      `test_jd_text_is_escaped`、`test_rationale_is_escaped`、`test_failed_confirm_leaves_stores_untouched`）
- [x] 全量测试通过，两个包 `tb validate` 0/0（720 passed，3 deselected；两包均 0 error / 0 warning；
      含最终评审修复波次）
- [x] 引擎模块不 import `career`（`test_engine_does_not_import_career`：mastery / schedule /
      evidence / contract / learning 均无 `testbridge.career` 引用）

**设计：** [P4.2 公司/JD 匹配](superpowers/specs/2026-10-26-p4.2-company-jd-design.md)

**验证命令（2026-10-26）：**

```text
$ .venv/Scripts/python -m pytest -q
720 passed, 3 deselected in 38.64s

$ .venv/Scripts/python -m testbridge.cli validate content-packs/ros2-qos
0 error(s), 0 warning(s)        # exit 0

$ .venv/Scripts/python -m testbridge.cli validate content-packs/sample-sensors
0 error(s), 0 warning(s)        # exit 0
```

---

## P4.3 求职管理（已完成，2026-10-26）

**范围：**

- `application` 单表：公司、岗位、渠道、状态、投递日期、下一步动作与日期、笔记。
- 状态：`draft / applied / screening / interviewing / offer / rejected / withdrawn`；
  结束态不再计入到期跟进，但不禁止继续编辑。
- `/applications`：列表、状态筛选、状态计数、到期跟进、创建表单。
- `/applications/{id}`：详情、编辑、快捷撤回。
- 纯本地 SQLite、无 LLM、引擎零改动；投递记录不影响 readiness/mastery/planner。
- 不提供删除；用 `withdrawn` 结束并保留历史。

**不做：** 自动投递、招聘网站爬虫、邮件/日历集成、多用户、与面试会话的强关联。

**退出标准（实测，2026-10-26）：**

- [x] `/applications` 可创建、列表、筛选、编辑、撤回
      （`tests/test_career_applications_web.py` 13 个测试：创建/列表/筛选/详情/编辑/撤回全流程）
- [x] 到期跟进正确显示；结束态与未来项不显示
      （`test_due_follow_up_lifecycle`：`next_action_at = 昨天` 时列表出现“到期跟进”与公司名；
      改为 `offer` 后同一日期不再出现）
- [x] 公司/岗位/笔记正确转义
      （`test_list_escapes_company`、`test_detail_renders_and_escapes`）
- [x] 非法状态/日期/空必填被拒绝（400）并保留输入
      （`test_create_validation_preserves_input`、`test_update_validation_preserves_input`）
- [x] 全量测试通过，两个包 `tb validate` 0/0（742 passed，3 deselected；两包均 0 error / 0 warning）
- [x] 引擎模块不 import `career`；readiness/mastery 不受投递记录影响
      （`test_quality_boundaries.py::test_engine_does_not_import_career`；投递记录不进 evidence，
      readiness/mastery 无新增输入）

**设计：** [P4.3 求职管理](superpowers/specs/2026-10-26-p4.3-job-applications-design.md)

**验证命令（2026-10-26）：**

```text
$ .venv/Scripts/python -m pytest -q
742 passed, 3 deselected in 43.65s

$ .venv/Scripts/python -m testbridge.cli validate content-packs/ros2-qos
0 error(s), 0 warning(s)        # exit 0

$ .venv/Scripts/python -m testbridge.cli validate content-packs/sample-sensors
0 error(s), 0 warning(s)        # exit 0
```

---

## 后续期摘要

P2、P3.1、P3.2、P3.3、P3.4、P3.5、P4.1、P4.2、P4.3 已实现。当前范围、退出标准与遗留以上方章节为准。

### P3 内容生产

- 资源检索：SearXNG / Firecrawl / arXiv 顺延（OpenAlex 已于 P3.3 完成）。
- AI 起草：按 `tb/1` 生成内容包，必须通过 validator。
- 质量门禁：引用、可信度、练习覆盖、目标级别。
- 内容包演进：跨草稿批量重生成已由 P3.5 完成；`tb migrate` 仍未开始。

### P4 应用整合

P4.1 与 P4.2 已合并到 master；P4.3 已完成（分支 `p4.3-job-applications`）。

- [P4.1 面试闭环](superpowers/specs/2026-10-26-p4.1-interview-loop-design.md)：已完成。
- [P4.2 公司/JD 匹配](superpowers/specs/2026-10-26-p4.2-company-jd-design.md)：已完成。
- [P4.3 求职管理](superpowers/specs/2026-10-26-p4.3-job-applications-design.md)：已完成。
- 能力结论仍只来自 evidence；面试会话、题库、JD 与投递记录属于过程状态，不是第二本账。

---

## 文档索引

- 总设计：[2026-10-24-teaching-engine-design.md](superpowers/specs/2026-10-24-teaching-engine-design.md)
- P3.1 内容工作台：[2026-10-25-p3.1-content-studio-design.md](superpowers/specs/2026-10-25-p3.1-content-studio-design.md)
- P3.2 质量门禁：[2026-10-25-p3.2-quality-gates-design.md](superpowers/specs/2026-10-25-p3.2-quality-gates-design.md)
- P3.3 检索后端：[2026-10-25-p3.3-search-backends-design.md](superpowers/specs/2026-10-25-p3.3-search-backends-design.md)
- P3.4 多模块与批量：[2026-10-25-p3.4-multi-module-batch-design.md](superpowers/specs/2026-10-25-p3.4-multi-module-batch-design.md)
- P3.5 内容演进：[2026-10-26-p3.5-content-evolution-design.md](superpowers/specs/2026-10-26-p3.5-content-evolution-design.md)
- P4.1 面试闭环：[2026-10-26-p4.1-interview-loop-design.md](superpowers/specs/2026-10-26-p4.1-interview-loop-design.md)
- P4.2 公司/JD 匹配：[2026-10-26-p4.2-company-jd-design.md](superpowers/specs/2026-10-26-p4.2-company-jd-design.md)
- P4.3 求职管理：[2026-10-26-p4.3-job-applications-design.md](superpowers/specs/2026-10-26-p4.3-job-applications-design.md)
- Agent 守则：[../CLAUDE.md](../CLAUDE.md)
- 开源项目调研：[research/ai-teaching-open-source.md](research/ai-teaching-open-source.md)
