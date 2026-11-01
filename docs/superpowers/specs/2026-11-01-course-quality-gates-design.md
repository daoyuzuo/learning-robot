# 课程质量门禁设计（teach skill 参考）

- 状态：Design approved，2026-11-01
- 范围：`quality/lint.py`、`tb lint`、`LessonManifest.objective_map`、
  作者 brief 模板、作者 skill
- 上游：[课程深度门禁](2026-11-01-depth-gate-design.md)、
  [Skill 驱动课程创作](2026-11-01-skill-based-authoring-design.md)
- 参考：[Matt Pocock teach skill](https://github.com/mattpocock/skills/blob/main/skills/productivity/teach/SKILL.md)

---

## 1. 问题

`tb depth` 只能拦住“太短”，拦不住“长而空”：没有主来源、没有工程实例、
目标与练习脱节、选择题靠格式泄漏答案。teach skill 的核心做法是先写 Mission、
再建 Resource map、每课只追一个 tangible win，并用检索练习和即时反馈建立
长期记忆。当前 `course-author` 缺少这些作者产物，`tb quality` 也不检查这些维度。

## 2. 目标

- 新增作者 brief 模板：Mission、Resources、Lesson brief。
- 新增 `tb lint <pack>`，检查：
  - 每课有 primary source（manifest 中第一条 required A/B 资源，且有 `why`）
  - 每课有带数字/单位的 worked example
  - objective 与 exercise 有显式映射（`LessonManifest.objective_map`）
  - 选择题答案位置和选项长度不过度失衡
  - 正文无占位符、无答案/解析泄漏
- 把 `tb lint` 接入作者交付流程。

## 3. 非目标

- 不引入 LLM 评审；红队评审、学生模拟仍作为可选人工/外部步骤。
- 不做学习记录（runtime 已有 evidence/mastery/review）。
- 不生成完整 glossary；概念术语仍用 `concepts.yaml`。
- 不改 `tb quality` 分数、不改渲染、不改学习运行时。

## 4. 决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | `objective_map` 作为 `LessonManifest` 可选字段 | 显式映射可确定性检查；不破坏旧包 |
| D2 | primary source = manifest 第一条 required A/B 资源 | 不新增字段；作者通过排序表达主次 |
| D3 | worked example 用“数字 + 单位”检测 | 跨学科、可执行；表格/图仍由 depth 检查 |
| D4 | quiz fairness 只做确定性启发式 | 位置集中和长度失衡是最明显的线索 |
| D5 | 新规则放在 `tb lint`，不并入 `tb quality` | 保持既有分数与测试稳定 |
| D6 | brief 产物放 `docs/course-briefs/<pack>/` | 作者层产物，不进入 `tb/1` 数据包 |

## 5. `objective_map`

```json
{
  "objectives": ["能解释风险分级", "能为场景做风险分级"],
  "objective_map": {
    "O1": ["EX-001-01"],
    "O2": ["EX-001-02"]
  }
}
```

- objective 按顺序命名为 `O1`、`O2`……
- key 必须匹配 `^O[1-9]\d*$`，value 必须非空，且引用的 exercise 必须在
  `manifest.exercises` 中。
- 未提供 `objective_map` 的旧包仍可加载；`tb lint` 对 L3/L4 报错，对 L1/L2 警告。

## 6. `tb lint` 规则

| 错误码 | 严重度 | 检查 |
|---|---|---|
| `lint.primary_source_missing` | error | 每课至少一条 required A/B 资源，且 `why` 非空 |
| `lint.no_worked_example` | L3/L4 error；L1/L2 warning | 正文出现数字 + 单位（ms/s/mm/cm/m/m·s⁻¹/%/°C/kg/Hz/N/N·m/rad/V/A/W） |
| `lint.objective_map_missing` | L3/L4 error；L1/L2 warning | manifest 缺 `objective_map` |
| `lint.objective_unmapped` | error | 某个 `O<n>` 没有映射到练习 |
| `lint.objective_exercise_unknown` | error | 映射引用了本课未列出的练习 |
| `lint.quiz_answer_position` | error | 单一正确选项位置占比 > 70% |
| `lint.quiz_option_length` | >3.0 error；>2.0 warning | 同一题选项长度 max/min 失衡 |
| `lint.quiz_answer_longest` | warning | 正确答案是最长选项的比例 > 60% |
| `lint.placeholder` | error | 正文含 `待填`/`TODO`/`TBD`/`example.com`/`lorem` |
| `lint.answer_leak` | error | 正文含 `"answer":`/`"explanation":`/`"accepted":`/`"rubric":` |

`tb lint` 退出码：0 全过；1 有 error；2 包无法加载。

## 7. 作者 brief 模板

`.claude/skills/course-author/references/` 新增：

- `mission-brief.md`：Why / Success looks like / Constraints / Out of scope。
- `lesson-brief.md`：tangible win / primary source / 先修检索题 / worked example /
  练习与误区 / 表或图 / 分钟数。

作者流程：

```text
Mission → Resources → 概念图与评估蓝图 → 每课 Lesson brief → 写正文
→ tb validate → tb depth → tb lint → tb quality → tb build
```

## 8. 测试

新增 `tests/test_quality_lint.py`：

- primary source 缺失报错
- 无数字单位报错（L3）
- objective_map 缺失/未映射/引用未知练习
- 答案位置集中报错
- 选项长度失衡 error/warning
- 占位符与答案泄漏
- `tb lint` 退出码 0/1/2 与 `--json`

全量 `pytest` 不回归。

## 9. 验收

- [ ] `tb lint content-packs/robot-quality-system` 退出 0
- [ ] `tb depth content-packs/robot-quality-system` 仍退出 0
- [ ] `tb validate` / `tb quality` / `tb build` 不回归
- [ ] `pytest` 全绿
- [ ] skill、authoring guide、CLAUDE.md、ROADMAP 与实现一致
