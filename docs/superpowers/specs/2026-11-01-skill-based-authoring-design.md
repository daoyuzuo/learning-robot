# Skill 驱动的课程创作设计

- 状态：Design approved，2026-11-01；实施中
- 范围：课程创作方式、Studio 生成层移除、作者 skill、`tb scaffold`
- 上游：[总设计](2026-10-24-teaching-engine-design.md)、
  [P3.1 内容工作台](2026-10-25-p3.1-content-studio-design.md)（退役）
- 路线图：[ROADMAP](../../ROADMAP.md)

---

## 1. 目标

把课程生成从框架内部移出，交给编程 AI（Claude Code 等）按 skill 直接写内容包；
框架只负责 `tb/1` 契约校验、渲染、学习运行时。

```
编程 AI 读取 .claude/skills/course-author/SKILL.md
  → 与作者澄清主题/边界
  → 用 WebSearch/WebFetch 查官方/权威资料
  → 设计课程结构（模块/课/难度/资源，由 AI 判断）
  → tb scaffold / 直接写 content-packs/<id>
  → tb validate → 修正 → tb quality（可选）→ tb build
  → 框架只加载、渲染、记录学习证据
```

- 不再由框架调用 LLM 生成课程。
- 不再有 Studio 后台任务、草稿、大纲/写课流水线、内部搜索路由。
- Runtime AI 保留：Tutor 联网追问、面试评分建议、JD 解析、求职记录。

## 2. 非目标

- 不把课程生成做成另一套框架内流水线；skill 是弱约束指令，不是代码分支。
- 不删除 Tutor / Interview / Career 运行时 AI。
- 不改 `tb/1` 契约、判分、掌握度、调度、证据。
- 不保留 Studio 的兼容层/旧页面；git 历史负责追溯。

## 3. 决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 删除 `src/testbridge/studio/` 与 Studio Web/测试 | 生成逻辑不再属于框架；减少维护面 |
| D2 | 课程由编程 AI 直接写 `content-packs/` | 生成过程透明、可 review、可 diff |
| D3 | skill 放 `.claude/skills/course-author/` | Claude Code 项目级自动发现；其他 AI 可读同一文件 |
| D4 | 提供 `tb scaffold <id>` | 确定性骨架，减少格式错误；不生成课程内容 |
| D5 | 框架只强约束 `tb/1` 契约 | 渲染/学习需要合法内容；教学质量靠 skill 弱约束 |
| D6 | `tb quality` 保留为可选建议 | 确定性检查，不调用 LLM；不作为生成流水线 |
| D7 | `verify-resources` 移到 `quality/verify.py` | Studio 删除后仍可检查资源链接 |

## 4. 保留与删除

**保留：**
- `contract/`、`content/`、`lesson/`、`build.py`、`artifact.py`、`widgets/`
- `learning/`、`evidence/`、`mastery/`、`schedule/`、`recommend/`、`readiness.py`
- `tutor/`（含联网追问）、`interview/`、`career/`
- `quality/`（确定性质量检查）
- 学习 Web 页面、Tutor/Interview/Career 页面
- `content-packs/test-quality-system`（作为示例包）

**删除：**
- `src/testbridge/studio/` 全部生成模块
- `web/studio.py`、Studio 模板、`studio.js`、`evolution.js`
- `web/app.py` 的 Studio 挂载、`studio_*` 参数
- `cli.py` 的 Studio 参数/导入
- 导航中的「工作台 / 演进」
- Studio 测试与 `studio.planning` 测试
- `studio.search_openalex` / `studio.search_router`；`testbridge/search.py` 保留给 Tutor
- `tb/1` 契约、渲染、学习代码不动

## 5. Skill 内容

`.claude/skills/course-author/SKILL.md`：
- frontmatter `name` / `description`
- 何时使用
- 输入：主题、大纲、参考资料、目标、现有包
- 对话澄清（不套固定表单）
- 官方资料检索：用编程 AI 自己的 WebSearch/WebFetch；记录 URL/许可证/验证日期
- 结构设计：模块/课/分钟/深度由 AI 判断，不设框架上限
- 写 `tb/1` 文件；不修改引擎
- 校验循环：`tb validate` → 修正 → `tb quality`（可选）→ `tb build`
- 交付：包路径、结构摘要、serve 命令

`references/`：
- `content-contract.md`：文件布局、manifest、练习类型、资源字段、允许标签
- `authoring-guide.md`：弱约束写作指南（目标、练习覆盖、来源、无答案泄漏、课程量自由）
- 示例指向 `content-packs/test-quality-system`

## 6. `tb scaffold`

- `tb scaffold <pack_id> --title ... --dir content-packs`
- 生成一个**能通过 `tb validate` 的最小包**：
  - `pack.yaml`、`concepts.yaml`、`exercises.yaml`、`resources.yaml`
  - `modules/M01/module.yaml`
  - `modules/M01/lessons/L-001-001.html`（manifest + 一个练习挂载点）
- 占位内容（待填概念/题目/资源），skill 负责替换。
- 不覆盖已有目录；ID 非法或目录存在时返回非 0。
- 不调用 LLM/网络。

## 7. 验收

- [ ] `.claude/skills/course-author/SKILL.md` 与 references 存在，包含 `tb scaffold` / `tb validate` / `content-packs/`。
- [ ] `tb scaffold demo --dir <tmp>` 生成的包 `tb validate` 0 error。
- [ ] 框架不再挂载 `/studio`；导航无「工作台/演进」。
- [ ] 运行时页面、Tutor、Interview、Career 测试不回归。
- [ ] `tb validate` / `tb build` / `tb serve` / `tb quality` 可用。
- [ ] `pytest` 全绿；旧 Studio 测试已删除。

## 8. 迁移

- Studio 代码/页面删除，git 历史保留。
- 现有 `content-packs/test-quality-system` 不变，继续可渲染/学习。
- 旧 Studio 文档保留为历史，不再作为实现依据。
- 学习证据不因删除 Studio 改变。
