# TestBridge — Agent 守则

> 修改任何代码前，先读：
> 1. `docs/ROADMAP.md`（当前期、硬规则、退出标准）
> 2. `docs/superpowers/specs/2026-10-24-teaching-engine-design.md`（P1 总设计）
> 3. `docs/superpowers/specs/2026-10-25-p2-learning-loop-design.md`（P2 学习闭环）
>
> 这三份是权威。`docs/research/` 只作参考，不是实现依据。

## 当前阶段

**2026-11-01 架构转向：框架内课程生成层已删除。** `src/testbridge/studio/`、`/studio`
页面、草稿、大纲/写课流水线、内容演进全部移除。课程改由编程 AI（Claude Code 等）读取
`.claude/skills/course-author/SKILL.md`，直接写 `content-packs/`；框架只负责 `tb/1`
契约校验、渲染与学习运行时。

P2 学习闭环与 P4.1–P4.3 运行时功能保留：Tutor 联网追问、面试评分建议、JD 解析、
求职记录继续可用。

### 课程创作（框架外）

- 编程 AI 用 skill 的弱约束工作：先澄清意图，再用自己的 WebSearch/WebFetch 查
  官方/权威资料，直接写 `content-packs/`。
- `tb scaffold <id>` 生成合法空包；`tb validate` 是硬契约；`tb quality` 是可选建议；
  `tb build` / `tb serve` 负责渲染与运行。
- Skill 是文档，不是框架内流水线。不要再向框架里加隐藏的生成器、LLM 大纲/写课循环或
  搜索路由；课程结构、课数、分钟由 AI 与作者判断。
- 内容包是数据：只能含 `tb/1` 文件，不得 import 引擎代码；引擎不得写死学科文本。
- 修改课程是数据变更：写文件 → `tb validate` → `tb build`；不要为内容改动引擎/契约。

### 运行时（保留）

- Tutor（含联网追问）、Interview、Career/JD、Applications 保留；它们服务学习/求职，
  不是课程生成。
- P4.2 的 `career/` 不得被 `mastery`、`schedule`、`evidence`、`contract`、`learning`
  import。
- P4.3 投递记录是过程状态，不参与 mastery/readiness/planner，不写 evidence。
- 运行时 AI 不直接写掌握度；任何“学会了”的结论仍必须能下钻到 evidence。

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

**作者层边界：** 课程创作发生在框架外（skill + 编程 AI），内容包只能包含 `tb/1` 数据，
不得 import 引擎代码。运行时 AI（Tutor / Interview / Career）可以有自己的提示词与模型调用，
但不得写掌握度、不得绕过 evidence。

## 内容契约速查

- 课程是 **HTML 片段 + 内嵌 JSON manifest**（`<script id="tb-manifest">`）。
- 练习定义在 `exercises.yaml`，课程只引用 `exercise` ID。
- 概念图在 `concepts.yaml`，资源在 `resources.yaml`。
- 校验分 error（阻断发布）和 warning（质量提示）。
- 内容按不可信输入处理：白名单标签/属性，禁止脚本、iframe、事件属性。
- widget 只能是引擎注册的渲染器，内容只提供 JSON 规格。

## 工作方式

- 先看现有目录和测试，再改；不要凭记忆重建。
- **课程创作：** 读 `.claude/skills/course-author/SKILL.md`，用 `tb scaffold` 起步，
  直接写 `content-packs/`；不要在框架内新增生成器/LLM 流水线。改完跑 `tb validate`、
  `tb depth`、`tb lint`、`tb build`。
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
- `tb depth content-packs/<id>` 通过：每课达到级别对应的字数、结构、图示和练习阈值
- `tb lint content-packs/<id>` 通过：主来源、数字实例、objective_map、题目公平性达标
- `tb rebuild-state` 可重复执行，增量与重建结果一致
- `/today` 给出带理由和预计时长的计划
- `/concepts` 显示掌握度、等级、目标、到期数
- `/review` 列出到期卡
- readiness 有总分、模块分、P0 门控原因
- 前端不再返回练习答案；跨课程 evidence 被拒绝
