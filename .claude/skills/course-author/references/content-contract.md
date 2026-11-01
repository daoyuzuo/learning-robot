# tb/1 内容契约速查

权威定义在 `src/testbridge/contract/models.py` 与 `validator.py`；
这里只列作者写文件时需要知道的字段。示例包：`tests/fixtures/packs/sample-sensors`。

## 目录

```
content-packs/<pack-id>/
  pack.yaml
  concepts.yaml
  exercises.yaml
  resources.yaml
  widgets.yaml                 # 可选
  assets/                      # 可选；本地图片/SVG
  modules/<module-id>/module.yaml
  modules/<module-id>/lessons/<lesson-id>.html
```

所有 YAML 顶层带 `schema: tb/1`。ID 规则：`^[A-Za-z][A-Za-z0-9-]*$`。

## pack.yaml

```yaml
schema: tb/1
id: my-course
version: 0.1.0
title: 课程标题
description: 一句话说明
language: zh-CN
license: CC-BY-4.0
authors: [author]
created: 2026-11-01
fixture: false
```

## concepts.yaml

```yaml
schema: tb/1
concepts:
  - id: core
    title: 概念标题
    domain: 领域
    target_level: L2
    prerequisites: []
    related: []
    weight: 1.0
    evidence_criteria:
      - {id: ev-core, description: 能解释并应用, level: L2}
    resources: [DOC-1]
```

- `target_level`/`level` 只能是 L1–L4；evidence criterion 的 level 不能超过 target。
- `prerequisites` 必须引用本文件存在的 concept id；不能有环。

## exercises.yaml

```yaml
schema: tb/1
exercises:
  - id: EX-1
    type: single_choice
    concepts: [core]
    level: L2
    prompt: 题干
    options: [{id: a, text: 选项 A}, {id: b, text: 选项 B}]
    answer: a
    explanation: 解析
    difficulty: 1
```

题型与额外字段：

- `single_choice`：`options` + `answer`（选项 id）。
- `multi_choice`：`options` + `answer`（非空选项 id 数组）。
- `short_answer`：`answer: {accepted: [...], min_hits: 1}` + `rubric`（weight 合计 1.0）。
- `self_assess`：`rubric`，不要 `answer`。
- `artifact`：`artifact` 规格 + `rubric`，不要 `answer`。

`hints` 可选，level 1–5 不能重复。`explanation` 用于答后反馈，不要把它写进正文。

## resources.yaml

```yaml
schema: tb/1
resources:
  - id: DOC-1
    title: 官方标准/文档标题
    url: https://example.com/
    type: official-doc
    kind: official_docs
    role: required
    trust: A
    license: 许可证
    last_verified: 2026-11-01
    coverage: [core]
    why: 工程上什么时候用
```

- `url` 必须 http(s)，只写真实可访问来源；`last_verified` 是 `YYYY-MM-DD`。
- `kind`：`official_docs` / `standard` / `engineering_blog` / `tutorial` /
  `repository` / `paper` / `book` / `video` / `other`。
- `role`：`required` / `supplementary`；`trust`：A/B/C/D。
- 课程 HTML 不要直接引用外部图片；课程 manifest 只引用 resource id。

## module.yaml

```yaml
schema: tb/1
id: M01
title: 模块标题
priority: P1
concepts: [core]
lessons: [L-001-001]
order: 1
```

## 课程 HTML

```html
<script type="application/json" id="tb-manifest">
{
  "schema": "tb/1",
  "id": "L-001-001",
  "title": "课程标题",
  "module": "M01",
  "concepts": ["core"],
  "target_level": "L2",
  "minutes": 30,
  "objectives": ["学完能做什么", "能应用什么"],
  "prerequisites": [],
  "exercises": ["EX-1", "EX-2"],
  "resources": ["DOC-1"],
  "objective_map": {"O1": ["EX-1"], "O2": ["EX-2"]}
}
</script>
<article class="tb-lesson">
  <h1>课程标题</h1>
  <p>正文。</p>
  <div data-tb-exercise="EX-1"></div>
  <div data-tb-exercise="EX-2"></div>
</article>
```

- 正文只用允许标签：`article/section/div/h1-h4/p/ul/ol/li/strong/em/code/pre/a/
  table/thead/tbody/tr/th/td/aside/figure/figcaption`（以及 `img` 指向包内 `assets/`）。
- 禁止 `script`/`style`/`iframe`/事件属性；正文会被 sanitizer 处理。
- `objective_map` 可选：按 `objectives` 顺序把 `O1..On` 映射到本课练习；
  `tb lint` 对 L3/L4 课要求提供，且引用的练习必须在 `exercises` 中。
- 每个 manifest 里的 exercise 必须在正文有且只有一个空的
  `<div data-tb-exercise="..."></div>` 挂载点；不能挂载未列出的练习。
- widget 只能使用 `widgets.yaml` 中注册的 `parameter-svg`，正文放
  `<div data-tb-widget="..."></div>`；不要写脚本。

## 校验

```bash
tb validate content-packs/<id>     # 硬契约；必须 0 error
tb quality content-packs/<id>      # 可选建议
tb build content-packs/<id> --out dist
```
