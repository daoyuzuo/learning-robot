# 课程深度门禁设计

- 状态：Design approved，2026-11-01
- 范围：`quality/depth.py`、`tb depth`、作者 skill 与完成定义
- 上游：[Skill 驱动课程创作](2026-11-01-skill-based-authoring-design.md)、
  [总设计](2026-10-24-teaching-engine-design.md)
- 路线图：[ROADMAP](../../ROADMAP.md)

---

## 1. 问题

`tb validate` 只检查 `tb/1` 契约，`tb quality` 只检查结构、覆盖与资源。两者都不关心
课程正文有多深，所以 500 字的提纲式课程也能拿到 `0 error` 与 `100/100`。
2026-11-01 重建 `robot-quality-system` 时，第一版 21 课平均正文仅 532 字，就是
“结构全绿、内容很浅”的直接结果。

需要一条确定性的、可执行的深度门禁，把“课要讲透”从弱约束变成硬检查。

## 2. 目标

- 新增 `tb depth <pack>`：逐课检查正文篇幅、结构、图示/表格和练习数量。
- 低于阈值返回非 0，可用于作者交付前自检和 CI。
- 不改 `tb/1` 契约，不改 `tb validate`，不改 `tb quality` 评分。
- 不调用 LLM，不做课程生成流水线。

## 3. 非目标

- 不判断内容“写得好不好”；只检查可确定的结构与篇幅代理指标。
- 不强制固定标题文字；用 `<h2>` 数量、表格/图示和练习数做代理。
- 不对测试夹具强制门禁；`tests/fixtures/packs/*` 仅作格式参考。
- 不做每包自定义阈值；阈值集中在代码中，后续确有需要再加。

## 4. 决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 独立 `tb depth` 命令 | 不改变现有 validate/quality 语义与分数 |
| D2 | 按课级别设阈值 | L3/L4 要求更高，L1/L2 允许短课 |
| D3 | 统计去标签后的非空白字符 | 稳定、可复现；不依赖渲染 |
| D4 | 不计 manifest 脚本 | 避免把 JSON 元数据算进正文 |
| D5 | 用 `<h2>`、表格/图示、练习数做结构代理 | 跨学科可执行，不绑定固定标题 |
| D6 | 夹具不纳入门禁 | 夹具用于契约测试，不是交付课程 |
| D7 | 作者流程强制跑 `tb depth` | 让门禁真正进入交付闭环 |

## 5. 阈值

| 课级别 | 最少字数 | 最少 `<h2>` | 最少表格 + 图示 | 最少练习 |
|---|---|---|---|---|
| L1 | 1,200 | 3 | 0 | 2 |
| L2 | 2,000 | 4 | 0 | 2 |
| L3 | 3,500 | 6 | 1 | 2 |
| L4 | 4,500 | 7 | 1 | 2 |

“字数”定义为：课程 `<script id="tb-manifest">` 之后正文 HTML 去掉标签、
去掉空白后的字符数。代码块、表格文字和列表文字都计入。

## 6. CLI 契约

```text
tb depth <pack>
tb depth <pack> --json
```

人类可读输出：

```text
OK   L-001-001 L3 chars=4117 h2=12 tables=3 figures=0 exercises=2
FAIL L-002-003 L3 chars=1200 h2=3 tables=0 figures=0 exercises=2
     depth.lesson_too_short: 1200 < 3500
     depth.too_few_sections: 3 < 6
1 lesson(s), 2 error(s)
```

退出码：

- `0`：全部课程通过
- `1`：至少一条深度错误
- `2`：包不存在、契约无效或无法加载

错误码：

- `depth.lesson_too_short`
- `depth.too_few_sections`
- `depth.no_table_or_figure`
- `depth.too_few_exercises`

## 7. 模块边界

新增 `src/testbridge/quality/depth.py`：

- 输入：已加载的 `ContentPack`
- 输出：`DepthReport`（逐课 `LessonDepth` + `issues` + `ok`）
- 依赖：`content.repository`、`contract.models`；不依赖 `mastery`、`schedule`、
  `learning`、`evidence`、`career`
- 纯函数式评估，不做 I/O、不调用网络/LLM

CLI 只做参数解析、打印和退出码；评估逻辑全部在 `depth.py`。

## 8. 作者流程

`.claude/skills/course-author/SKILL.md` 的校验循环改为：

```text
tb validate content-packs/<id>   # 硬契约
tb depth content-packs/<id>      # 深度门禁
tb quality content-packs/<id>    # 可选建议
tb build content-packs/<id> --out dist
```

作者交付前必须让 `tb depth` 退出 0。`tb quality` 仍为可选建议，不替代深度门禁。

## 9. 测试

新增 `tests/test_quality_depth.py`：

- 短课触发 `lesson_too_short`
- 长课但 `<h2>` 不足触发 `too_few_sections`
- L3 课缺表格/图示触发 `no_table_or_figure`
- 练习少于 2 道触发 `too_few_exercises`
- manifest JSON 与 HTML 标签不计入字数
- 不同级别使用不同阈值
- `tb depth` 退出码 0/1/2
- `--json` 输出可解析

全量 `pytest` 不得回归。

## 10. 验收

- [ ] `tb depth content-packs/robot-quality-system` 退出 0，21 课全部通过
- [ ] `tb depth tests/fixtures/packs/sample-sensors` 退出 1（夹具不满足，属预期）
- [ ] `tb validate content-packs/robot-quality-system` 仍为 `0 error(s), 0 warning(s)`
- [ ] `tb quality content-packs/robot-quality-system` 仍为 `100/100`
- [ ] 全量 `pytest` 通过
- [ ] skill、authoring guide、CLAUDE.md、ROADMAP 与实现一致

## 11. 迁移与兼容

- 现有内容包无需改字段；不满足阈值的包会第一次看到 `tb depth` 失败。
- 测试夹具不接入 CI 的 depth 步骤，避免契约测试被内容深度绑架。
- 旧的 `tb quality` 输出与分数保持不变。
