# 课程写作弱约束

这些是判断准则，不是框架强制的流水线。课程量、结构和来源由作者与编程 AI 共同决定。

## 0. 先写 Mission 与 Lesson brief

参考 Matt Pocock `teach` skill 的做法：

- `docs/course-briefs/<pack>/MISSION.md`：Why / Success looks like / Constraints / Out of scope。
- `docs/course-briefs/<pack>/RESOURCES.md`：Knowledge / Wisdom / Gaps，每条资源写用途。
- `docs/course-briefs/<pack>/lessons/<lesson-id>.md`：tangible win、primary source、
  先修检索题、带数字的 worked example、objective → exercise 映射、误区、表/图、分钟。

没有 Mission 和目标岗位，不要开始写正文；没有 Lesson brief，不要开始写单课。

## 1. 先确定课程边界

- 必须覆盖什么？明确不讲什么？
- 学完能独立完成什么任务？
- 目标岗位/场景、已有基础、评估方式。
- 先给结构提案，再写文件；不要一上来堆 50 节课。

## 2. 先查官方/权威资料

- 用 WebSearch/WebFetch 查标准、官方文档、官方仓库、权威书籍。
- 标准号、版本、发布日期要能落到真实 URL；不要把模型记忆当来源。
- 记录 `last_verified`、`license`、`why`；找不到官方来源时明确告诉作者缺口，
  不要用博客冒充标准。
- 资源优先 A/B；C 只作补充；D 不作为 required。

## 3. 结构自由，教学优先

- 模块数、每模块课数、单课分钟不设上限；按内容需要决定。
- 先修关系要真实；不要为了凑模块把概念拆碎。
- 每课围绕一个可检验的学习成果；先讲清问题，再讲方法，再给判断标准。
- 允许“短课 + 多课”或“长课 + 少课”；在交付说明里解释取舍。

## 3.1 深度下限

- 每课至少达到 `tb depth` 的级别阈值（L3 默认 3,500 字、6 个 `<h2>`、1 个表格/图、2 道练习）。
- 一节完整的课应包含：工程场景、概念与边界、方法步骤、机器人实例与数字、判定与证据、
  常见误区、检查清单、小结。
- 交付前必须跑 `tb depth`；少于阈值时补实质内容，不要用重复段落凑字数。

## 4. 练习设计

- 每课至少 2 道，覆盖本课每个概念；至少 1 道达到课程 target_level。
- 混合题型：选择考辨析，简答考解释/设计，自评考反思；不要全是记忆题。
- 题干给足上下文；答案与解析放在 `exercises.yaml`，不要写进正文。
- rubric 维度要可判定；短答的 accepted 关键词要覆盖合理同义表达。
- 选择题选项长度尽量接近；正确答案位置在模块内分散；不要靠格式或顺序泄漏答案。
- 每个选择题至少一个“像真答案”的误区干扰项；每课 manifest 写 `objective_map`。

## 5. 资源与引用

- 每课至少 1 条 required A/B 资源；尽量包含官方标准/官方文档。
- `why` 写“工程上什么时候用”，不要写“很好/很详细”。
- 资源覆盖的 concept 要真实对应；不要给整门课挂一条泛泛链接。
- 课程正文只引用 resource id，不直接嵌外部图片/脚本。

## 6. 修改已有课程

- 先看 `concepts.yaml` / `exercises.yaml` / `resources.yaml` 与现有学习证据。
- 改 concept/exercise ID 会让旧证据失去对应概念/题目；能保留就保留，必须改时说明影响。
- 删除课程包会删除内容，但不会自动清空学习记录；提醒作者。
- 改完必须重新 `tb validate`；结构/资源变化后跑 `tb build` 检查渲染。

## 7. 交付

给作者：课程包路径、结构摘要、官方来源与缺口、`tb validate` / `tb depth` / `tb lint`
结果、serve 命令。不要声称“已完成”而没有跑过这三项门禁。
