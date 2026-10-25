# TestBridge — Agent 守则

> 修改任何代码前，先读：
> 1. `docs/ROADMAP.md`（当前期、硬规则、退出标准）
> 2. `docs/superpowers/specs/2026-10-24-teaching-engine-design.md`（P1 总设计）
> 3. `docs/superpowers/specs/2026-10-25-p2-learning-loop-design.md`（P2 学习闭环）
>
> 这三份是权威。`docs/research/` 只作参考，不是实现依据。

## 当前阶段

**P3.1 已完成并合并到 `master`。** `/studio` 提供“主题 → 大纲 → 调研 → 写课 → 校验 → 定稿”工作台，产物是普通 `tb/1` 包，引擎零改动。

**当前 P3.2（质量门禁）设计已批准，待实现。** 规则、分值与验收见
`docs/superpowers/specs/2026-10-25-p3.2-quality-gates-design.md`。

**不要提前实现：**

- P3.3–P3.5：检索后端、批量/多模块、内容演进
- P4：面试 / 公司情报 / 求职管理

除非用户明确要求并先更新 ROADMAP。

**P3.1 附加边界：**

- `src/testbridge/studio/` 不得 import `mastery`、`schedule`、`learning`、`evidence`。
- 模型输出与检索结果按不可信输入处理：先解析、再 `sanitize_fragment`、后落盘。
- 密钥只从 `TESTBRIDGE_LLM_*` 环境变量读取，不落盘、不回显、不写日志。
- 草稿在 `drafts/`（已 gitignore）；默认 `pytest` 不联网，真实调用需 `TESTBRIDGE_LIVE=1`。

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
