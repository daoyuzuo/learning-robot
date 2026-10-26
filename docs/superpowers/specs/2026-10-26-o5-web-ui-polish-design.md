# O5 页面排版与样式（Design）

- 状态：Implemented，2026-10-26
- 范围：`web/static/tb.css`、Jinja2 模板、独立构建页面样式
- 上游：[优化清单](../../OPTIMIZATION.md)
- 决策：优先级最低，可增量做；本轮只做 CSS + 模板类名，不引入前端框架。

---

## 1. 背景

全站只有一个约 100 行的 `tb.css`，token 只有 5 个变量
（[tb.css:1-4](../../../web/static/tb.css#L1-L4)）；顶栏是一行链接
（[base.html:10-13](../../../web/templates/base.html#L10-L13)）；固定阅读宽度
860px；没有深色模式、焦点样式、移动端折叠、表格滚动容器；工作台状态只有文字。

目标：在不改变信息架构和交互逻辑的前提下，让页面看起来像一个成品，
在窄屏、键盘操作和深色模式下都可用。

---

## 2. 非目标

- 不引入 React/Vue/Tailwind 或任何前端构建链。
- 不重写页面信息架构，不新增复杂交互。
- 不做完整设计系统文档站点。
- 不改业务路由、请求参数、数据模型。
- 不做浏览器端视觉回归测试；以手工验收 + 关键 class 断言为主。

---

## 3. 设计 token

在 `:root` 定义，深色模式覆盖：

```css
:root {
  --tb-bg: #ffffff;
  --tb-surface: #f8fafc;
  --tb-ink: #1f2937;
  --tb-muted: #6b7280;
  --tb-line: #e5e7eb;
  --tb-accent: #2563eb;
  --tb-success: #047857;
  --tb-warning: #b45309;
  --tb-danger: #b91c1c;

  --tb-radius-sm: 6px;
  --tb-radius-md: 8px;
  --tb-radius-lg: 12px;
  --tb-space-1: .25rem;
  --tb-space-2: .5rem;
  --tb-space-3: .75rem;
  --tb-space-4: 1rem;
  --tb-space-6: 1.5rem;
  --tb-space-8: 2rem;

  --tb-font-sans: system-ui, -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
  --tb-font-mono: ui-monospace, SFMono-Regular, Consolas, monospace;
  --tb-text-sm: .875rem;
  --tb-text-base: 1rem;
  --tb-text-lg: 1.125rem;
  --tb-text-2xl: 1.5rem;
}

@media (prefers-color-scheme: dark) {
  :root {
    --tb-bg: #0f172a;
    --tb-surface: #1e293b;
    --tb-ink: #e2e8f0;
    --tb-muted: #94a3b8;
    --tb-line: #334155;
    --tb-accent: #60a5fa;
    --tb-success: #34d399;
    --tb-warning: #fbbf24;
    --tb-danger: #f87171;
  }
}
```

兼容：现有 `--ink` / `--muted` / `--line` / `--accent` / `--bg` 保留为别名，
避免一次性改所有模板。

---

## 4. 布局

### 4.1 顶栏

- 桌面：品牌 + 导航一行，导航项有 hover/focus 状态。
- 窄屏（`max-width: 760px`）：导航换行或收进 `<details>`；不引入 JS。
- 当前页高亮：由 `request.url.path` 在模板中加 `aria-current="page"`。

### 4.2 内容区

- `tb-main` 默认 `max-width: 1100px`；
- 课程阅读页使用 `.tb-lesson-main`，`max-width: 72ch`，行高 1.75；
- 工作台/列表页使用全宽，表格外层 `.tb-table-wrap { overflow-x: auto; }`；
- 统一 `padding` 与 `padding-bottom`，避免底部按钮贴边。

### 4.3 课程页

- 标题层级、段落间距、`figure` / `figcaption` 样式；
- 代码块 `pre` 横向滚动，`code` 使用等宽字体；
- 练习卡、反馈块、资源列表统一卡片样式；
- 长课目录（可选，后做）：从 `h2` 生成，先不做，避免改渲染器。

---

## 5. 组件

新增/统一以下 class，模板逐步替换：

| 组件 | class | 说明 |
|---|---|---|
| 按钮 | `.tb-btn`, `.tb-btn-primary`, `.tb-btn-ghost` | hover/focus/disabled 状态 |
| 卡片 | `.tb-card` | 边框、圆角、内边距 |
| 徽章 | `.tb-badge`, `[data-status="pending/running/done/failed"]` | 状态色 + 文本，不只靠颜色 |
| 进度条 | `.tb-progress-bar` | 批量/长任务进度 |
| 提示块 | `.tb-callout`, `[data-tone="info/warn/error"]` | 替代裸文本错误 |
| 表格 | `.tb-table-wrap` | 横向滚动 |
| 图 | `.tb-figure`, `.tb-figure figcaption` | 居中、说明文字 |
| 表单 | `.tb-form`, `.tb-field` | label 与输入框统一间距 |
| 目录 | `.tb-toc` | 预留，不在本轮实现 |

工作台状态：

- `pending` 灰色、`running` 蓝色 + 进度条、`done` 绿色、`failed` 红色；
- 状态文本仍保留，颜色只是辅助。

---

## 6. 可访问性

- 所有可交互元素有 `:focus-visible` 轮廓；
- 表单控件有 `<label>` 关联；
- 正文/背景对比度达到 WCAG AA；
- 支持 `prefers-reduced-motion: reduce`（关闭过渡）；
- 320px 宽度无横向滚动；
- 颜色不是唯一状态信号（徽章带文字）；
- 跳过导航链接（可选，加分项）。

---

## 7. 模板改动

| 文件 | 改动 |
|---|---|
| `web/templates/base.html` | 顶栏结构、当前页高亮、跳过链接、`main` class |
| `web/templates/lesson.html` | 阅读宽度 class、图/表/代码块样式钩子 |
| `web/templates/dashboard.html`、`today.html`、`concepts.html`、`review.html`、`progress.html` | 卡片/表格/徽章 class |
| `web/templates/studio_*.html` | 步骤卡、状态徽章、进度条、计划卡片（O4） |
| `web/templates/interview_*.html` | 表单/卡片/维度表统一 |
| `web/templates/applications*.html`、`target*.html` | 表单/提示块统一 |

只加 class 与少量结构化元素，不改表单字段名和路由。

---

## 8. 构建与离线页

- `tb build` 内联同一份 `tb.css`（[build.py:232-234](../../../src/testbridge/build.py#L232-L234)），
  自动继承新样式。
- 独立页不含外部字体/CDN，保持离线可用。
- O2 的 `.tb-figure` 样式在 O2 与 O5 中都要存在；先由 O2 加最小样式，
  O5 统一。

---

## 9. 测试与验收

自动化：

- `pytest` 现有 Web 测试不回归；
- 关键页面断言包含统一 class（如 `tb-card`、`tb-badge`），避免模板回退；
- 不新增视觉回归依赖。

手工验收：

- 320 / 768 / 1280 三档：无横向滚动，导航可用，表格可滚动；
- 键盘 Tab 走完课程提交、工作台主要按钮、表单保存；
- 深色模式下正文、表格、练习反馈、SVG 图可读；
- `tb build` 产物样式与 Web 一致；
- 对比改动前后的截图，记录在 PR/提交说明中。

---

## 10. 实施顺序

1. token + 深色模式 + 基础排版（不影响结构）。
2. 按钮/表单/卡片/徽章/表格组件，替换高频页面。
3. 顶栏响应式与当前页高亮。
4. 工作台状态徽章与进度条。
5. 课程页图/代码/表格细节。
6. 手工三档验收与截图。
