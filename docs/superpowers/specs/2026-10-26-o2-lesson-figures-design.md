# O2 课程图文并茂（Design）

- 状态：Implemented，2026-10-27
- 范围：Studio 写课的确定性 SVG 图示；不改内容契约、不接外部图片、不接 AI 生图
- 上游：[优化清单](../../OPTIMIZATION.md)
- 决策：2026-10-26 确认本轮只做“结构化图形 → 服务端渲染 SVG”。

---

## 1. 背景

净化器和内容契约已经允许 `img` / `svg` / `figure`
（[sanitize.py:10-17](../../../src/testbridge/contract/sanitize.py#L10-L17)），
样例课也用了本地 `<img>`
（[L-SYNC-001.html:22-23](../../../content-packs/sample-sensors/modules/M01/lessons/L-SYNC-001.html#L22-L23)）。
但写课提示词的允许标签清单里没有 `img` / `svg`
（[prompts.py:30-31](../../../src/testbridge/studio/prompts.py#L30-L31)），
模型不会主动产图；同时 CSP 只允许本地/`data:` 图片
（[web/app.py:118-120](../../../web/app.py#L118-L120)），外部热链不可用。

目标：让生成出来的课在**离线、确定性、无版权风险**的前提下，具备框图、流程图、
时间线、对比图这类“思路图”，而不是装饰性插图。

---

## 2. 非目标

- 不做外部图片搜索/下载、不做授权署名流程。
- 不接 AI 生图模型，不新增 `TESTBRIDGE_IMAGE_*`。
- 不允许模型输出任意 SVG（只接受受限 JSON 规格）。
- 不做图形编辑器、不做自由拖拽。
- 不改 `tb/1` 内容契约；最终产物仍是普通 HTML + 内联 SVG。

---

## 3. 图形规格

写课输出 JSON 增加 `figures` 数组；每项：

```json
{
  "id": "FIG-1",
  "kind": "flow",
  "caption": "ROS2 测试链路",
  "alt": "从传感器到判定的四步流程图",
  "title": "可选标题",
  "concepts": ["sensor-time-sync"]
}
```

- `concepts` 可选，写图覆盖的概念 id；必须是本课声明概念的子集，否则报错。

`kind` 与专属字段：

### 3.1 `flow`

```json
{
  "nodes": [{"id": "n1", "label": "采集"}, {"id": "n2", "label": "回放"}],
  "edges": [{"from": "n1", "to": "n2", "label": "可选"}],
  "direction": "LR"
}
```

- `direction`：`LR` 或 `TB`，默认 `LR`。
- 节点 2–8 个；边只能引用已声明节点；允许分支，不做复杂环路布局。

### 3.2 `timeline`

```json
{
  "events": [{"at": "t0", "label": "发送", "detail": "可选"}]
}
```

- 事件 2–8 个，按数组顺序排列；`at` 是短标签（时间/阶段），不做真实时间计算。

### 3.3 `block`

```json
{
  "groups": [
    {"label": "感知", "items": ["相机", "IMU"]},
    {"label": "判定", "items": ["规则", "模型"]}
  ]
}
```

- 分组 1–4 个，每组 1–5 项；渲染为分组框。

### 3.4 `compare`

```json
{
  "left": {"title": "仿真", "items": ["可重复", "成本低"]},
  "right": {"title": "实车", "items": ["真实噪声", "成本高"]}
}
```

- 每侧 1–5 项；渲染为左右两栏。

所有字符串长度上限：`label` 40 字、`detail` 80 字、`caption/alt` 200 字；
超出由解析层拒绝并触发模型重试。

---

## 4. 挂载与渲染

### 4.1 写课输出

模型在 HTML 中放空挂载点：

```html
<div data-tb-figure="FIG-1"></div>
```

规则：

- 每个 figure 恰好一个挂载点；
- 挂载点必须在 `<article class="tb-lesson">` 内；
- 正文不得直接写 `<img src="http...">` 或任意 `<svg>`；
- 挂载点位置应紧跟相关段落，而不是全部堆在文末。

### 4.2 解析与渲染

新增 `src/testbridge/studio/figures.py`：

```python
class FigureError(Exception): ...

def parse_figures(items: object) -> list[dict]: ...
def render_figure(spec: dict) -> str: ...
def embed_figures(html: str, figures: list[dict]) -> str: ...
```

流程：

1. `parse_lesson_json` 解析 `figures`，校验 `id` 唯一、`kind` 合法、字段数量与长度、
   `concepts` 是本课概念的子集；
2. 校验 HTML 中每个挂载点都有对应规格，且每个规格都有挂载点；
3. `render_figure` 生成内联 SVG：
   - 固定 `viewBox`（如 `0 0 800 320`），`width="100%"`，`role="img"`；
   - `<title>` / `<desc>` 来自 `caption` / `alt`；
   - 颜色用 `currentColor` 与少量语义色，兼容深色模式；
   - 文字自动换行（按字符宽度估算，中文按 2 个半角计）；
   - 不使用 `<style>`、`<script>`、事件属性、外部字体；
4. `embed_figures` 把挂载点替换为：

```html
<figure class="tb-figure">
  <svg ...>...</svg>
  <figcaption>caption</figcaption>
</figure>
```

5. 渲染结果再走 `sanitize_fragment`，然后写盘。

净化器需要同步扩展（仍是白名单，不放宽脚本/事件属性）：

- `ALLOWED_TAGS` 增加 `title`、`desc`（SVG 可访问性节点）；
- `ALLOWED_ATTRIBUTES` 增加 `role`、`aria-label`、`aria-describedby`、
  `aria-hidden`、`focusable`；
- 保持禁止 `style`、`script`、事件属性、外部 URL；
- 新增测试确认上述属性保留、`on*` 与 `style` 仍被移除。

失败处理：

- 规格非法、挂载点缺失/重复 → `LessonError`，由现有 `generate()` 重试一次；
- 重试仍失败 → 该课 `failed`，错误信息包含 figure id 与原因；
- 不回退成“静默删除图”，避免用户以为生成了图。

---

## 5. 提示词与版本

`LESSON_SYSTEM` 更新：

- 允许的 HTML 标签增加 `figure` / `figcaption`；仍禁止模型直接写 `svg` / `img`；
- 每课 1–2 张图；纯概念课至少 1 张，流程/架构/时间线主题优先；
- 每张图必须有 `caption` 与 `alt`，且 `alt` 描述“图表达了什么关系”；
- 图形只使用本课概念，不引入其它课程/模块的概念；
- 输出格式增加 `"figures": [...]`；挂载点用 `data-tb-figure`。

`OUTLINE_SYSTEM` 可选增加：`exercise_intents` 之外标注哪些课适合配图
（先不做，避免扩大变更面）。

prompt 版本：按实施顺序 O3 先落地为 `studio/3`，O2 为 `studio/4`。
`studio/version.py` 更新；P3.5 的版本记录与测试同步调整。旧草稿保持旧版本，
不自动迁移。

---

## 6. 质量与校验

- `tb validate`：不新增硬错误；最终 HTML 中的 SVG 已由净化器允许。
- `tb quality`：
  - 新增 warning `quality.lesson_no_figure`：仅对草稿中
    `prompt_version >= studio/4` 的课程检查；`evaluate_draft` 读取 `draft.json`
    的 `steps.lessons[*].prompt_version`，已发布包没有该元数据时跳过。
    这只是 warning，不影响分数；
  - 新增 hard error `quality.figure_mount_unresolved`：最终 HTML 仍存在
    `data-tb-figure` 挂载点（说明渲染链路漏了）；
  - 不改变现有分数基线；图示覆盖先只做 warning。
- 统计：写课结果记录 `figure_count`，P3.5 快照对比增加该字段（可选）。
- 清理：`replace=True` 重写课程时，旧 HTML 中的 figure 随之替换；不需要单独的
  资源清理（SVG 内联在 HTML 里）。

---

## 7. 样式与构建

- 新增 `.tb-figure` / `.tb-figure svg` / `.tb-figure figcaption` 样式
  （随 O5 的样式工作一起落地，O2 先给最小样式）。
- SVG 内联，不新增 `assets/` 文件；`tb build` 的单文件产物直接包含图，
  不引入额外资源。
- 深色模式下用 `currentColor`，避免写死黑/白。

---

## 8. 测试

| 层 | 覆盖 |
|---|---|
| 解析 | 四种 kind 的合法/非法字段；数量上下限；字符串长度；id 重复 |
| 渲染 | 每种 kind 生成 `<svg>`、`<title>`、`<desc>`、`<figcaption>`；中文标签不丢 |
| 挂载 | 正常替换；缺规格/重复挂载/多余规格报错；挂载点在 article 外报错 |
| 净化 | 渲染结果经 `sanitize_fragment` 后仍保留 SVG 结构；无脚本/事件属性 |
| 写课 | 假 LLM 返回含 figures 的课程 → 写盘 HTML 含内联 SVG；失败重试一次 |
| 质量 | 旧 prompt 版本不检查；新版本无图给 warning；未解析挂载点硬错误 |
| 回归 | 现有 742 个测试；两个包 `tb validate` 0/0；`tb quality` 基线不降 |

验收：

- 新建 2 模块 × 2 课，写课后每课至少 1 张图；
- `tb validate` 0/0，`tb quality` 不产生新的硬错误；
- 页面与 `tb build` 产物离线显示图，无外部请求；
- 默认 `pytest` 全绿且不联网。

---

## 9. 后续（不在本轮）

- 外部图片搜索、下载、授权与署名（第二层）。
- AI 生图（第三层，`TESTBRIDGE_IMAGE_*`，默认关闭）。
- 图形编辑器与手动改图。
