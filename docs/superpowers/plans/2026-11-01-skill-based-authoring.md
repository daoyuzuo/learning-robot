# Skill 驱动课程创作实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> or superpowers:executing-plans.

**Goal:** 删除框架内课程生成层，新增作者 skill 与 `tb scaffold`，框架只保留契约/渲染/学习。

**Architecture:** 课程由编程 AI 直接写 `content-packs/`；`.claude/skills/course-author/`
提供弱约束指令与契约参考；`tb scaffold` 生成合法空包；Studio 代码/页面/测试全部移除。

**Spec:** [Skill 驱动的课程创作](docs/superpowers/specs/2026-11-01-skill-based-authoring-design.md)

## Global Constraints

- 不改 `tb/1` 契约、判分、掌握度、调度、证据。
- 保留 Tutor（含联网）、Interview、Career 运行时 AI。
- Studio 生成层全部删除；不保留兼容层。
- Skill 是弱约束文档，不是框架内分支；框架只强约束 `tb/1`。
- `tb scaffold` 不调用 LLM/网络，不覆盖已有目录。
- 默认 `pytest` 不联网；旧 Studio 测试删除。
- 未经用户明确要求不执行 `git commit`。

---

### Task 1：`tb scaffold`

**Files:** 新建 `src/testbridge/scaffold.py`、`tests/test_cli_scaffold.py`；
修改 `src/testbridge/cli.py`。

- `scaffold_pack(root, pack_id, title, description="", level="L2") -> Path`。
- 生成最小合法包：pack/concepts/exercises/resources/M01/module.yaml/M01/lessons/L-001-001.html。
- CLI：`tb scaffold <pack_id> --title ... --dir content-packs`；已有目录/非法 ID 返回 2。
- 测试：生成后 `validate_pack` 0 error；重复/非法 ID 不写盘。
- 不依赖 Studio。

### Task 2：作者 skill

**Files:** `.claude/skills/course-author/SKILL.md`、
`references/content-contract.md`、`references/authoring-guide.md`、
`tests/test_authoring_skill.py`。

- frontmatter `name: course-author` + 描述。
- 指令覆盖：输入/澄清/官方资料检索/自由结构/写 `tb/1`/校验循环/不改引擎。
- references 写清文件布局、manifest、题型、资源、允许标签、弱约束写作指南。
- 测试：文件存在、frontmatter、包含 `tb scaffold`/`tb validate`/`content-packs/`；
  指向 `content-packs/test-quality-system` 示例。

### Task 3：删除 Studio 生成层与页面

**Files:** 删除 `src/testbridge/studio/`、`web/studio.py`、
`web/templates/studio_*.html`、`web/static/studio.js`、`web/static/evolution.js`；
修改 `web/app.py`、`src/testbridge/cli.py`、`web/templates/base.html`；
移动 `studio/verify.py` → `quality/verify.py`。

- `create_app` 删除 `studio_*` 参数与 mount；interview/target 的 LLM 配置回落到 `config`。
- `_load_app` 删除 studio 参数。
- `cli.py` 的 `verify-resources` 改从 `quality.verify` 导入。
- 导航删除「工作台 / 演进」。
- 保留 `testbridge/search.py` 供 Tutor；删除 `search_openalex`/`search_router`。

### Task 4：测试与文档收口

- 删除 `tests/test_studio_*.py`、`tests/test_planning.py`、
  `tests/test_search_openalex*.py`、`tests/test_search_router.py`。
- 更新 `tests/test_cli_verify.py` 的 verify 导入；检查运行时测试无 Studio 引用。
- 全量 `pytest`；`tb validate` 现有包 0/0；`tb build`/`serve` 冒烟。
- README：删除 Studio 章节，增加「课程由编程 AI + skill 创作」「tb scaffold」。
- ROADMAP：标记 Studio 生成层退役，新增 skill 创作阶段。
- 不提交 git，除非用户明确要求。
