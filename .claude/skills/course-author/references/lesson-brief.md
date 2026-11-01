# Lesson Brief 格式

每课一页，存放于 `docs/course-briefs/<pack>/lessons/<lesson-id>.md`。
写正文前先写 brief；brief 不清楚，正文一定空泛。

## 模板

```md
# {Lesson title}

## Tangible win
{学完能独立完成的一件具体事情，一句话。}

## Primary source
{RESOURCES.md 中的一条 A/B 来源；写明本课用它的哪一部分。}

## Retrieval
- {来自先修概念的 2–3 道回忆题}
- {……}

## Worked example
{带数字/单位的完整示例：条件、步骤、结果、判定。}

## Exercises
| Objective | Exercise | Misconception |
|---|---|---|
| O1 | EX-... | {本课要纠正的常见误区} |
| O2 | EX-... | {……} |

## Figure / table
{1 张表或图，说明它表达的关系；写清 caption。}

## Minutes
{45–60}
```

## 规则

- **一个 tangible win。** 一课只追一个核心成果；多个不相关目标应拆课。
- **必须有 primary source。** 优先 A/B 官方标准、官方文档或官方仓库。
- **必须有数字实例。** 至少一个带单位/数量的完整示例，不能只有概念。
- **必须有误区。** 每课至少一个练习针对“看起来像正确答案”的误解。
- **objective → exercise 显式映射。** 写进 lesson manifest 的 `objective_map`。
- **先写 brief 再写正文。** brief 阶段就能发现课太薄或目标太多。
