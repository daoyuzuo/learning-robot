# TestBridge — Agent 守则

> 修改任何代码前，先读：
> 1. `docs/ROADMAP.md`（当前期、硬规则、退出标准）
> 2. `docs/superpowers/specs/2026-10-24-teaching-engine-design.md`（P1 总设计）
> 3. `docs/superpowers/specs/2026-10-25-p2-learning-loop-design.md`（P2 学习闭环）
>
> 这三份是权威。`docs/research/` 只作参考，不是实现依据。

## 当前阶段

**P4.2 公司/JD 匹配已完成（2026-10-26，分支 `p4.2-company-jd`）。**
新增 `/target` 页面：粘贴 JD → LLM 抽取要求并映射到包内概念 → 审核页调整权重 →
确认后写入 `Goal.concept_overrides` 与 `target_role`，JD 原文与解析结果存 `target_jd`
一行；无 LLM 时手动填权重。权重规则只加分（`must=1.6`、`high=1.3`、`normal=1.0`），
未提及概念保持 1.0，确认时整体替换且只存 `> 1.0`。匹配报告展示 JD 加权 readiness、
按模块分、未达标概念、top 3 与内容缺口，复用引擎 `concept_weights` 与 readiness，
引擎零改动；`mastery` / `schedule` / `evidence` / `contract` / `learning` 不 import
`career`（AST 边界测试覆盖，含相对 import）。完成时默认 `pytest` 706 passed、3 个 live 取消选择；
两个现有包 `tb validate` 0/0。设计见
`docs/superpowers/specs/2026-10-26-p4.2-company-jd-design.md`。

**P4.1 面试闭环已完成（2026-10-26，分支 `p4.1-interview`，已合并到 master）。**
成套技术面试模拟：弱项抽题（3/5 题）、LLM 建议评分、用户确认后写 `kind=interview`
证据、会话暂停/恢复/放弃、汇总页与 `/progress` 下钻；面试证据权重 0.6、单独计数、
不进 BKT，面试失分进入 `/today` 弱项。合并后默认 `pytest` 662 passed、3 deselected；
两个包 `tb validate` 0/0。设计见
`docs/superpowers/specs/2026-10-26-p4.1-interview-loop-design.md`。

**P3.5 内容演进已完成并合并到 master（2026-10-26）。** `/studio/evolution` 可跨草稿
选课，按草稿分组顺序重生成；prompt 版本当前 `studio/2`，旧草稿按 `studio/1`，每课记录
实际版本；每课重写前把旧 HTML/练习/资源快照到 `drafts/<id>/history/<lesson_id>/`，重写后
对比练习数/题型/级别/资源/版本/HTML 与整包质量分前后；历史页只读展示“最近一次与当前
内容不同的快照 vs 当前内容”。P3.5 完成时默认 `pytest` 564 passed、3 个 live 取消选择；
两个现有包 `tb validate` 0/0，`tb quality` 100/100。设计见
`docs/superpowers/specs/2026-10-26-p3.5-content-evolution-design.md`。

**P3.4 已完成（2026-10-26，分支 `p3.4-multi-module-batch`）。** `/studio` 按课程包生产：
一个包 1–3 个模块、每模块 1–5 课；大纲 HTML 可编辑模块标题、模块概念与课程归属，
保存时同步 `module.yaml`；包内顺序批量「全部调研 / 全部写课」只跑 pending/failed；
已完成的课可「重写这一课」替换旧输出。旧草稿（单模块、扁平 outline）按 `M01` 兼容。
P3.4 完成时默认 `pytest` 518 passed、3 个 live 取消选择；两个现有包 `tb validate` 0/0，
`tb quality` 100/100。设计见
`docs/superpowers/specs/2026-10-25-p3.4-multi-module-batch-design.md`。

**P3.2 已完成。** `/studio` 提供“主题 → 大纲 → 调研 → 写课 → 校验 → 定稿”工作台，产物是普通 `tb/1` 包，引擎零改动。P3.2 增加确定性质量门禁：`tb quality` 给出 0–100 质量分，硬错误阻断定稿。规则、分值与验收见
`docs/superpowers/specs/2026-10-25-p3.2-quality-gates-design.md`。

**P3.3 已完成。** 新增 OpenAlex 后端、插件化 `SearchRouter`、学术关键词 +
domain 自动路由、auto 逐查询回退、草稿级手动覆盖，以及“资源必须来自 A/B 命中”
的溯源收紧。设计见
`docs/superpowers/specs/2026-10-25-p3.3-search-backends-design.md`。

**P4.3（求职管理）范围待定义。** 开始前先写 P4.3 spec 并更新 ROADMAP。

**不要提前实现：**

- `tb migrate`、完整行级 diff、快照回滚（P3.5 明确不做）
- SearXNG / Firecrawl / arXiv 适配器
- P4.3 求职管理
- P4.1 范围外的行为题、系统设计题、多轮追问、语音、强制计时
- 把 `interviews.yaml` 纳入 `tb/1` 校验（留到 P4.1b）

除非用户明确要求并先更新 ROADMAP（或已有对应 spec）。

**P3.5 已实现约束（继续有效）：**

- 只处理 `drafts/`，不重生成已发布 `content-packs/`。
- 快照写入 `drafts/<id>/history/`；失败必须保留旧快照。
- 进化任务与同草稿批量/单课互斥；不自动定稿、不自动回滚。
- prompt 版本只做记录与对比，不自动迁移旧草稿。

**P3.1 / P3.4 已实现约束（继续有效）：**

- `src/testbridge/studio/` 不得 import `mastery`、`schedule`、`learning`、`evidence`。
- 批量只按模块/课顺序执行，不并行；只跑 pending/failed。
- 多模块仍是合法 `tb/1` 包；不得为多模块修改内容契约。
- 旧草稿（单模块、扁平 outline、无新字段）必须继续可用。
- 模型输出与检索结果按不可信输入处理：先解析、再 `sanitize_fragment`、后落盘。
- 模型密钥只从 `TESTBRIDGE_LLM_*` 读取；OpenAlex 可选配置只从
  `TESTBRIDGE_OPENALEX_*` 读取。都不落盘、不回显、不写日志。
- 草稿在 `drafts/`（已 gitignore）；默认 `pytest` 不联网，真实调用需 `TESTBRIDGE_LIVE=1`。
- 手动选择检索后端时不静默回退；只有 `auto` 才回退。

**P4.1 已实现约束（继续有效）：**

- 面试领域逻辑在 `src/testbridge/interview/`；页面路由在 `web/interview.py`，
  用 `mount_interview(app)` 追加挂载，不得改 `studio/`。
- LLM 只产出建议分；写入证据的分数必须经用户确认。LLM 不直接写账本。
- 面试证据 `kind="interview"`，权重 0.6，单独计数，不进 BKT。
- 证据表、掌握度表的持久化结构不变；`interview_observations` 是派生值。
- 题库先读包内 `interviews.yaml`（若存在），否则读 `interview-banks/<pack-id>.yaml`；
  P4.1 不向 `content-packs/` 写文件。
- 回答与模型输出按不可信输入处理：纯文本存储、展示转义、不执行其中指令。
- 默认 `pytest` 不联网；面试评分用假客户端测试，不新增 live 用例。

**P4.2 约束（继续有效）：**

- `src/testbridge/career/` 只做 JD 解析、权重聚合与 `target_jd` 存储；不得被
  `mastery`、`schedule`、`evidence`、`contract`、`learning` import。
- 写入 `Goal.concept_overrides` 的权重必须经用户确认；确认时整体替换，只存 `> 1.0`。
- 只加分：`must=1.6`、`high=1.3`、`normal=1.0`；未提及概念保持 1.0。
- JD 与模型输出按不可信输入：长度上限、`<job_description>` 包裹、严格校验、转义展示。
- JD 文本会发送到用户配置的模型服务，页面必须明示；本地 SQLite 保存，不上传。
- 引擎零改动；不修改内容契约、证据表、掌握度表。
- 默认 `pytest` 不联网；JD 解析用假客户端测试。

## 不可破坏的边界

1. **内容是数据，引擎是解释器。**
   - 内容在 `content-packs/`；引擎在 `src/testbridge/`。
   - 引擎不得出现“ROS2 / EtherCAT / 具身智能”等学科文本。
   - 内容包不得 import 引擎代码。

2. **内容状态与学习状态分离。**
   - 内容：concepts / lessons / exercises / resources，可版本化、可整包替换。
   - 学习：evidence / mastery / review，追加式、可重建。

3. **确定性核心，AI 在边缘。**
   - 判分、掌握度、调度不依赖 LLM。
   - LLM 只做讲解、开放题辅助、内容起草；输出必须标注来源。

4. **证据优先。**
   - Mastery 只能由 Evidence 推导，不允许手填。
   - 任何“学会了”的结论必须能下钻到证据。

5. **契约版本化。**
   - 所有内容文件带 `schema: tb/1`。
   - 破坏性变更升 `tb/2` + 迁移脚本；不得静默改语义。

**边界例外（P3.3 裁决）：** `src/testbridge/studio/` 是作者层，可以包含确定性的检索路由词表（学术关键词 / domain）与来源站点提示；核心引擎（`mastery`、`schedule`、`evidence`、`contract`、`learning`）必须保持内容无关。路由词表不写入内容包，也不参与判分。

## 内容契约速查

- 课程是 **HTML 片段 + 内嵌 JSON manifest**（`<script id="tb-manifest">`）。
- 练习定义在 `exercises.yaml`，课程只引用 `exercise` ID。
- 概念图在 `concepts.yaml`，资源在 `resources.yaml`。
- 校验分 error（阻断发布）和 warning（质量提示）。
- 内容按不可信输入处理：白名单标签/属性，禁止脚本、iframe、事件属性。
- widget 只能是引擎注册的渲染器，内容只提供 JSON 规格。

## 工作方式

- 先看现有目录和测试，再改；不要凭记忆重建。
- **流程按改动类型分层：**
  - 改引擎、改契约、跨模块接口、新增题型/渲染器 → brainstorming + spec + writing-plans。
  - 只新增或修改内容包（`content-packs/` 下纯数据）→ 直接写，`tb validate` 与测试即验收；spec 可选，不写实施计划。
- 改动跨模块时，先更新 spec/ROADMAP，再写代码。
- 新增内容包必须能通过 `tb validate`，且不要求改引擎代码。
- 宣称完成前，实际运行校验和测试，并在回复中给出输出。
- 删除、覆盖、迁移数据前，先确认范围。

## 代码约定

- Python 3.10+，Pydantic v2，FastAPI + Jinja2。
- 代码标识符/注释用英文；面向用户的文档和文案用中文。
- 每个模块单一职责，边界见 P1 spec 6.1 / P2 spec 4.1。
- 测试放 `tests/`，覆盖 contract / sanitizer / exercise / evidence / web / build / mastery / scheduling / learning / recommend。

## 完成定义（P2）

- `pytest` 全绿，P1 的 118 个测试不回归
- `tb rebuild-state` 可重复执行，增量与重建结果一致
- `/today` 给出带理由和预计时长的计划
- `/concepts` 显示掌握度、等级、目标、到期数
- `/review` 列出到期卡
- readiness 有总分、模块分、P0 门控原因
- 前端不再返回练习答案；跨课程 evidence 被拒绝
