# ROS2 QoS 内容试点设计

- 状态：Approved，2026-10-25
- 范围：用 `tb/1` 契约写一个真实内容包，验证契约是否够用；不新增引擎能力
- 上游：[P1 教学引擎设计](2026-10-24-teaching-engine-design.md)、[P2 学习闭环](2026-10-25-p2-learning-loop-design.md)
- 路线图：[ROADMAP](../../ROADMAP.md)

---

## 1. 目的

P1/P2 的内容都是契约夹具（`sample-sensors`），只证明格式能跑通，不证明它适合真实学习材料。

本试点写一个真实包：面向“车身电子/ECU 测试 → 具身智能测试”转型者，ROS2 零基础，目标岗位需要能独立验证通信链路的质量。

试点要回答三个问题：

1. 3 节课 + 6 道练习的体量，契约字段够不够表达教学目标？
2. 只有 `parameter-svg` 一种 widget 时，能不能做出有意义的交互图？
3. 写真实内容时，哪条校验规则会误报、哪条会漏报？

## 2. 非目标

- 不改引擎代码、不新增 widget 渲染器、不改 `tb/1`。
- 不做 P3 的资源检索或 AI 起草；内容由人工按契约写。
- 不覆盖 ROS2 全貌（执行器、生命周期、DDS 调优留后续）。
- 不做 artifact 练习（产出物评分尚未实现）。

## 3. 内容包

```
content-packs/ros2-qos/
  pack.yaml
  concepts.yaml
  exercises.yaml
  resources.yaml
  widgets.yaml
  modules/M01/
    module.yaml
    lessons/L-QOS-001.html
    lessons/L-QOS-002.html
    lessons/L-QOS-003.html
  assets/widgets/qos-queue.svg
```

- `id: ros2-qos`，`schema: tb/1`，`version: 0.1.0`，`language: zh-CN`，`license: CC-BY-4.0`。
- 只有模块 `M01`，`priority: P0`（通信是后续所有内容的地基，未达目标时 readiness 应被门控）。

## 4. 概念图

| id | 标题 | 级别 | 权重 | 先修 |
|---|---|---|---|---|
| `ros2-communication-model` | 话题、服务、动作的边界 | L2 | 1.0 | — |
| `dds-qos-policies` | DDS QoS 策略 | L3 | 1.2 | `ros2-communication-model` |
| `qos-compatibility` | offered vs requested 兼容性 | L2 | 1.0 | `dds-qos-policies` |
| `qos-observability` | QoS 观测手段 | L2 | 0.8 | `qos-compatibility` |
| `qos-testing` | 通信质量测试方法 | L3 | 1.2 | `qos-compatibility`, `qos-observability` |

每个概念带 2 条 `evidence_criteria`，覆盖“说清楚”和“测出来”两个层次；`level` 不高于 `target_level`。

`related` 只在确有横向联系时填写（`qos-testing` ↔ `qos-observability`）。

## 5. 课程

| lesson | 标题 | 分钟 | 目标级别 | 概念 | 练习 |
|---|---|---|---|---|---|
| `L-QOS-001` | 通信模型：话题、服务、动作 | 18 | L2 | `ros2-communication-model` | `EX-QOS-001` |
| `L-QOS-002` | QoS 策略与兼容性 | 25 | L3 | `dds-qos-policies`, `qos-compatibility` | `EX-QOS-002`, `EX-QOS-003`, `EX-QOS-005` |
| `L-QOS-003` | QoS 观测与测试 | 25 | L3 | `qos-compatibility`, `qos-observability`, `qos-testing` | `EX-QOS-004`, `EX-QOS-006` |

每节课的结构固定：

1. 一段“为什么这和测试有关”的开场，不只讲 API。
2. 正文要点（列表 + 代码块，代码块用 `data-tb-block="code"`）。
3. 一个 callout：本课最容易踩的坑。
4. 练习占位符。
5. 资源区块。

课程正文的中文表述遵守：先给判断标准，再给例子，最后给测试方法。

## 6. 练习

| id | 类型 | 级别 | 概念 | 考点 |
|---|---|---|---|---|
| `EX-QOS-001` | single_choice | L1 | `ros2-communication-model` | “持续反馈的长任务”该用 action 而不是 topic/service |
| `EX-QOS-002` | single_choice | L2 | `dds-qos-policies` | 高频传感器数据允许丢帧 → `BEST_EFFORT` |
| `EX-QOS-003` | multi_choice | L2 | `qos-compatibility` | 哪些 pub/sub 组合不会建立连接 |
| `EX-QOS-004` | short_answer | L2 | `qos-observability` | 排查“订阅端收不到数据”的步骤 |
| `EX-QOS-005` | self_assess | L2 | `dds-qos-policies` | `depth` 与 `lifespan` 的区别 |
| `EX-QOS-006` | single_choice | L3 | `qos-testing` | 怎么判定 deadline 违约 |

约定：

- 选择题的错误选项必须是“真实会犯的错”，不是凑数。
- `short_answer` 的 `accepted` 用 2–4 字的关键词，`min_hits` 取一半、向上取整，避免误判。
- `self_assess` 的 rubric 两个维度、权重和 1.0，必须对应“机制”和“检测方法”。
- 每题带 1–2 条分级提示，提示不直接给答案。

## 7. 资源

全部 ROS 2 官方文档或 OMG 规范，`trust: A`，带 `license` 与 `last_verified: 2026-10-25`。写作前逐条请求确认可达；不可达的换成可达的一手来源，不降级为博客。

| id | 覆盖概念 |
|---|---|
| `DOC-ROS2-COMM` | `ros2-communication-model` |
| `DOC-QOS-SETTINGS` | `dds-qos-policies`, `qos-compatibility` |
| `DOC-DDS-SPEC` | `dds-qos-policies` |
| `DOC-ROS2-TOPIC-CLI` | `qos-observability` |
| `DOC-QOS-TUTORIAL` | `qos-testing` |

`why` 字段必须说明“这份材料能回答什么问题”，不能只写“官方文档”。

## 8. 交互图

`W-QOS-QUEUE`，`type: parameter-svg`，模板 `assets/widgets/qos-queue.svg`。

- 参数：`drain`（订阅端处理间隔，0.5–2.0，默认 1.0）。
- 图：一条发布流（固定间隔的 6 个消息方块）+ 一组按 `transform="scale({{drain}}, 1)"` 缩放的消费标记。
- 语义：`drain` 变大 → 两次消费之间积压更多消息 → 超过 `KEEP_LAST depth` 时旧消息被丢弃。
- 图注必须写出“改大参数看什么”，让滑块有明确意图。

选择 `parameter-svg` 的理由：试点要验证内容层，不引入引擎变更。若后续发现表达力不足（例如需要按 reliability 切换两种视图），再升级到新渲染器。

## 9. 验收

- `tb validate content-packs/ros2-qos` 输出 `0 error(s), 0 warning(s)`。
- `tb build content-packs/ros2-qos --out <tmp>` 产出 3 个单文件 HTML。
- `pytest` 全绿，且不新增引擎代码；新增 `tests/test_ros2_qos_pack.py` 断言包能加载、概念/练习/资源数量与引用完整。
- Web：`/lesson/L-QOS-002` 能渲染，练习表单、提示、资源齐全。
- `tb readiness --pack content-packs/ros2-qos` 在无证据时输出 0 分，且 P0 门控生效。

## 10. 契约发现记录

试点完成于 2026-10-25。写过一遍真实内容后的结论：

**够用的部分**

- 概念 / 先修 / `evidence_criteria` 能直接表达“说清楚”和“测出来”两层目标。
- 课程 manifest + 五种题型覆盖了本轮全部练习，没有需要正文代偿的字段。
- `trust` / `coverage` / `why` 三个资源字段足以支撑“为什么给这条资源”的判断。

**字段不足**

1. `Exercise` 没有 `title`，复习理由只能用题干（P2.1 已按此实现）。
2. 代码块只有 `data-tb-block="code"`，没有转义或高亮工具；内容里出现 `<`、`>` 必须手写实体，`tb validate` 不检查这一点。
3. 课程没有“适合什么基础”的字段，同一节课无法对零基础和转岗者做难度分层。

**校验缺口**

1. `last_verified` 只是作者声明，validator 不核验可达性。本轮靠人工逐条请求确认；`docs.ros.org/en/rolling/` 下的旧路径已经 404，说明资源失效是常态，P3 应把可达性做成门禁。
2. spec 把“练习难度与概念目标级别不匹配”列为 warning，但 validator 没有实现。
3. 课程正文里的外部链接不检查，与资源表两套标准。

**引擎扩展候选（不在本轮）**

1. `parameter-svg` 只能做字面替换，无法表达离散状态：reliability 的两种行为、兼容矩阵高亮都做不出来。本轮用“处理间隔 → 队列积压”绕开，表达力有限。
2. 没有内容预览命令，作者必须 `tb serve` 或 `tb build` 才能看渲染结果，写作回路偏长。

## 11. 风险

| 风险 | 取舍 |
|---|---|
| 内容技术错误比代码错误更难发现 | 每个结论回链 A 级资源；术语首次出现给英文原名 |
| 只有一种 widget，交互图表达力弱 | 接受；把不足记入第 10 节，不在本轮加渲染器 |
| 3 节课覆盖面仍窄 | 试点目标是验证契约，不是覆盖 ROS2 |
| 资源链接失效 | 写作时逐条核验；`last_verified` 用实际核验日期 |
