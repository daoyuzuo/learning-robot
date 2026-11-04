# TestBridge 全站视觉焕新（Design）

- 状态：Approved（方向已定），2026-11-03
- 上游：本次对话的三个实物方向稿（`ui-audit/mockups/a.png` / `b.png` / `c.png`）
- 决策：采用 **C（克制的现代产品）作为骨架 + B（编辑部式阅读）作为课程正文排版**
- 范围：`web/static/tb.css`、`web/templates/*.html`、`web/static/*.js`（仅样式钩子）、
  `src/testbridge/concept_graph.py`、`src/testbridge/build.py`（样式与资源钩子）
- 不改：路由、请求参数、数据模型、`tb/1` 契约、判分/掌握度/调度/证据语义

---

## 1. 背景与问题

现状（截图见 `ui-audit/before/`）的问题**不是缺 CSS，是缺信息设计**：

| 页面 | 具体问题 |
|---|---|
| `/` 首页 | 13 个 P0 门控概念压成一整段长句；最弱概念是裸 `<ul>`；模块只有标题+链接列表，零进度可视化；21 课全平铺，看不出"我现在在哪" |
| `/concepts` | 表头 `掌握度/等级/目标/到期` 被挤成竖排换行；先修关系用英文 ID 直接铺在单元格里；SVG 图节点文字被截断成 `Flakiness …` |
| `/today` | 一条计划占满 1400px 宽度，右侧 70% 空白；`new` 徽章直接显示内部枚举值 |
| `/progress` | 证据表以英文 ID 为主列，时间戳是原始 ISO 串 |
| `/review` | 到期日直接打印 ISO 时间戳 |
| 课程页 | 正文可读但偏窄偏灰，练习卡/提示/追问区层次弱，`M01 · 测试策略…` 与正文 h1 重复 |
| 顶栏 | 8 个纯文字链接，无图标、无品牌元素、无分组，8 项在 760px 以下换行成两行 |

统一症状：**内部标识符泄漏到界面**（`test-strategy-inputs`、`new`、ISO 时间戳）、
**数字缺可视化**、**表头被压成竖排**。

## 2. 目标 / 非目标

**目标**

1. 首屏 3 秒内回答三个问题：我学到哪了、今天做什么、还差什么。
2. 课程正文适合连续 45–55 分钟阅读：字号、行高、阅读宽度、段落节奏重新调。
3. 界面只出现自然语言，不出现英文内部 ID、枚举值、ISO 时间戳。
4. 窄屏 320px 无横向滚动，键盘可走完，深色模式全站可读。
5. 离线 `tb build` 产物与 Web 完全同款。

**非目标**

- 不引入前端框架、SPA、构建链、CDN。
- 不重写路由与业务逻辑，不新增数据模型。
- 不改 `tb/1` 契约，不动判分/掌握度/调度语义。
- 不做浏览器视觉回归自动化（以脚本截图 + 人工走查为验收）。

## 3. 关键约束（决定素材怎么用）

1. **CSP 是 `style-src 'self'; script-src 'self'`**（`web/app.py` 安全头）。
   → 不能内联 `<style>`/`<script>`，不能 `<link>` 外部 CDN。
2. **离线优先**：`tb build` 输出单文件 HTML，必须零外部请求。
   → 素材必须**下载进仓库**，不能运行时拉取。
3. **净化器白名单**（`contract/sanitize.py`）禁止 `style`、事件属性、`script`、`iframe`。
   → 课程正文里的装饰只能用**白名单内的标签 + class**。
4. **中文字体没有衬线体**：本机只有 `Microsoft YaHei` / `Noto Sans SC` / `SimSun`，
   没有 Noto Serif SC / Source Han Serif。
   → 中文标题**不套用衬线体**（SimSun 小字号发虚，大字号老气），改用**字号 + 字重 + 字距**
   建立层级；衬线体只用于拉丁字符与数字（`Charter`/`Georgia` 回退）。

## 4. 素材方案（含许可证）

| 素材 | 来源 | 许可证 | 落地方式 |
|---|---|---|---|
| 图标 | Lucide Icons | ISC（Feather 派生部分 MIT） | 只取用到的约 20 个，**内联为 SVG symbol sprite**，随模板渲染 |
| 图标（备选） | Tabler Icons | MIT | 不采用，仅记录备选 |
| 字体 | 系统字体栈 | — | 不下载字体，`system-ui` + `Microsoft YaHei` + `Noto Sans SC` 栈 |
| 插图 | 自绘内联 SVG | 本项目 | 空状态、学习路径示意图 |

**放弃的选项**：Google Fonts / 任何 CDN（违反 CSP 与离线）；图标字体（额外请求 + 锯齿）；
Tailwind / shadcn 构建链（违反"无前端框架"）。

图标以 `web/templates/_icons.html` 作为 Jinja 宏文件提供 `icon(name, size)`，同时
`build.py` 内联同一份 sprite 供离线页使用。许可证文本写入 `web/static/LICENSES.md`。

## 5. 设计 token

在 `:root` 重写，深色模式通过 `@media (prefers-color-scheme: dark)` 覆盖；
同时提供 `[data-theme="light"]` / `[data-theme="dark"]` 供手动切换扩展（本轮不做切换 UI）。

```css
:root {
  /* 表面 */
  --tb-bg: #f7f7f8;          /* 浅灰画布 */
  --tb-bg-elevated: #ffffff; /* 卡片/面板 */
  --tb-bg-sunken: #f1f1f3;   /* 内嵌区块、表头 */
  /* 文字 */
  --tb-ink: #111113;
  --tb-ink-2: #3f3f46;       /* 次级正文 */
  --tb-muted: #71717a;       /* 说明文字 */
  --tb-faint: #a1a1aa;       /* 极弱 */
  /* 线 */
  --tb-line: #e4e4e7;
  --tb-line-soft: #f1f1f3;
  /* 强调 */
  --tb-accent: #4f46e5;
  --tb-accent-ink: #4338ca;  /* 文字用，保证 AA */
  --tb-accent-soft: #eef2ff;
  /* 语义 */
  --tb-success: #16a34a; --tb-success-soft: #f0fdf4;
  --tb-warning: #b45309; --tb-warning-soft: #fffbeb;
  --tb-danger:  #dc2626; --tb-danger-soft:  #fef2f2;
  /* 形状 */
  --tb-radius-sm: 8px; --tb-radius-md: 12px; --tb-radius-lg: 16px; --tb-radius-pill: 999px;
  /* 间距（4px 基准） */
  --tb-space-1: 4px; --tb-space-2: 8px; --tb-space-3: 12px;
  --tb-space-4: 16px; --tb-space-5: 20px; --tb-space-6: 24px;
  --tb-space-8: 32px; --tb-space-10: 40px; --tb-space-12: 48px;
  /* 字体 */
  --tb-font-sans: system-ui, -apple-system, "Segoe UI", "Microsoft YaHei",
                  "Noto Sans SC", "PingFang SC", sans-serif;
  --tb-font-serif: Charter, Georgia, Cambria, "Times New Roman", serif; /* 仅拉丁/数字 */
  --tb-font-mono: ui-monospace, "Cascadia Code", Consolas, monospace;
  /* 字号（1.2 比例，中文按 px 取整） */
  --tb-text-xs: 11px; --tb-text-sm: 12.5px; --tb-text-base: 14px;
  --tb-text-md: 15px; --tb-text-lg: 17px; --tb-text-xl: 20px;
  --tb-text-2xl: 24px; --tb-text-3xl: 30px;
  /* 层 */
  --tb-shadow-sm: 0 1px 2px rgb(0 0 0 / .04);
  --tb-shadow-md: 0 4px 16px rgb(0 0 0 / .06);
}
```

深色模式覆盖（默认跟随系统）：

```css
@media (prefers-color-scheme: dark) {
  :root {
    --tb-bg: #0b0b0d; --tb-bg-elevated: #141417; --tb-bg-sunken: #1a1a1f;
    --tb-ink: #ededf0; --tb-ink-2: #b4b4bd; --tb-muted: #8b8b95; --tb-faint: #5c5c66;
    --tb-line: #26262c; --tb-line-soft: #1e1e24;
    --tb-accent: #818cf8; --tb-accent-ink: #a5b4fc; --tb-accent-soft: #1e1b3a;
    --tb-success: #4ade80; --tb-success-soft: #10231a;
    --tb-warning: #fbbf24; --tb-warning-soft: #241c0b;
    --tb-danger: #f87171; --tb-danger-soft: #2a1214;
    --tb-shadow-sm: 0 1px 2px rgb(0 0 0 / .4);
    --tb-shadow-md: 0 4px 16px rgb(0 0 0 / .5);
  }
}
```

**兼容**：保留 `--ink` / `--muted` / `--line` / `--accent` / `--bg` 别名指向新 token，
旧规则不断裂。

**对比度**：`--tb-ink` on `--tb-bg-elevated` ≈ 17:1；`--tb-muted` ≈ 5.5:1；
`--tb-accent-ink` on `--tb-accent-soft` ≈ 7:1。深色同理，全部达 WCAG AA。

## 6. 版式系统

### 6.1 顶栏

- 高度 56px，sticky，`backdrop-filter: blur(12px)` + 半透明背景。
- 左：品牌（24px 方块 mark + 文字 `TestBridge`）。
- 中：导航**分组为三簇**，`数据`（今日/概念/复习/进度）· `应用`（面试/目标/求职）· `内容`（课程）。
  簇间用 1px 分隔线，不显示簇标题（空间不足时只呈现为视觉间隔）。
- 右：当前内容包名（点击回首页）。
- 当前页：`background: --tb-accent-soft; color: --tb-accent-ink`（pill 形）。
- `≤760px`：导航横向滚动（`overflow-x:auto` + `scrollbar-width:none`），不换行成两行。
- 保留 skip-link 与 `aria-current="page"`（`test_web_ui.py` 断言依赖）。

### 6.2 内容容器

- 默认 `max-width: 1120px`，`padding: 40px 28px 88px`。
- 课程页 `.tb-lesson-main` 改为 `max-width: 46rem`（约 736px ≈ 68 个中文字符），
  但图文课允许 `--tb-reading-max` 提升到 54rem。
- 密集页面（概念/进度）走全宽 + 表格滚动容器。

### 6.3 课程正文（B 的排版）

- 正文 `font-size: 16.5px`（中文），`line-height: 1.85`，`letter-spacing: .01em`。
- `h1` 30px/650；`h2` 20px/600 + 上方 40px 留白 + **左侧 3px accent 竖线**作为章节标记；
  `h3` 17px/600。
- 段落 `margin: 0 0 1.15em`；列表 `padding-left: 1.4em`；`blockquote` 左线 2px + 斜体。
- `pre` 深色底（即使浅色模式也用 `#1a1a1f` 深底，代码更清晰），圆角 10px，内边距 16px。
- 首段 `.tb-lesson > p:first-of-type` 放大到 17.5px、颜色 `--tb-ink-2`，作为导语。
- 表格：圆角边框、表头 `--tb-bg-sunken`、单元格 12px/16px 内边距、斑马纹**不用**（用细线）。
- 对象清单 `.tb-objectives` 改为「本课目标」卡片：标题行 + 图标 + 列表，去左侧 4px 粗边。

## 7. 组件

| 组件 | 规格 |
|---|---|
| `.tb-card` | 白底 `--tb-bg-elevated`、1px `--tb-line`、`--tb-radius-md`、`--tb-shadow-sm`、内边距 20px |
| `.tb-kpi` | KPI 卡：11.5px 标签 + 27px 数字（数字用 `--tb-font-serif`）+ 12px 说明 |
| `.tb-stat-row` | KPI 横排网格，`grid-template-columns: repeat(auto-fit, minmax(150px, 1fr))` |
| `.tb-progress-ring` | SVG 圆环，`stroke-dasharray` 驱动，中心大数字；用于 readiness |
| `.tb-meter` | 细条形掌握度指示，6px 高，圆角 |
| `.tb-badge` | pill，11.5px，语义色用 `-soft` 底 + 深色文字；**必须带文字**，颜色只是辅助 |
| `.tb-btn` | 中性按钮：`--tb-bg-sunken` 底；`.tb-btn-primary`：`--tb-ink` 底白字（C 方向的黑色主按钮）；`.tb-btn-ghost` 透明 |
| `.tb-callout` | 左侧 3px 语义色线 + `-soft` 底，圆角 10px；`[data-tone=info/warn/error/success]` |
| `.tb-table-wrap` | 横向滚动；表格 `min-width: 640px` 保证表头不竖排；表头 `white-space: nowrap` |
| `.tb-empty` | 空状态：居中图标 + 一句说明 + 主行动按钮 |
| `.tb-section-title` | 区块标题：16px/600 + 右侧计数/操作，下方 14px 间距 |
| `.tb-list-row` | 通用行：图标槽 + 主文本 + 次文本 + 右侧操作 |
| `.tb-field` | label 12.5px/500 上置，input 40px 高、8px 圆角；焦点环 `2px --tb-accent` |
| `.tb-tabs` | 状态筛选 pill 组（求职/复习使用），当前项深底白字 |

**表头竖排的根因**：原表格无 `min-width`，浏览器把 `掌握度` 折成三行。修复为
`th { white-space: nowrap }` + `.tb-table-wrap table { min-width: 640px }`，
密集表可达 `min-width: 880px` 并横向滚动。

## 8. 逐页改造

### 8.1 首页 `/`（C 的仪表盘）

结构：标题区 → KPI 行 → 门控条 → 今日计划 + 最弱概念（两栏）→ 模块列表（两栏）。

- **KPI 行**：4 张卡 —— Readiness（大卡，带圆环/进度条 + 门控上限说明）、到期复习、
  今日计划项与总分钟、已掌握概念 `n / 总数`。
- **门控条**：`tb-callout[data-tone=warn]`，文案改为「门控生效：13 个 P0 概念未达 L3，
  readiness 上限 0.70」，后接「查看拆解 →」链接到 `/progress`；
  **不再罗列 13 条 `xxx 估计 L0，目标 L3`**，改为计数 + 可展开 `<details>`。
- **今日计划**：取 `plan.items` 前 2 条，`tb-list-row` 展示：图标 + 课程标题（自然语言）
  + 理由 + 分钟数 + 「开始」主按钮。
- **最弱概念**：3 行，概念标题（不是 ID）+ `tb-meter` + `L0 · 目标 L3`。
- **模块区**：每模块一卡，卡头为模块标题 + `0 / 7`，下方 4px 进度条，再列课程行
  （状态圆点 + 标题 + 分钟）。宽屏两栏，窄屏一栏。

### 8.2 今日 `/today`

- 顶部：预算/已排分钟以 `tb-stat-row` 呈现。
- 计划项：`tb-list-row`，类型徽章用中文（`复习`/`新学`/`补弱`），理由保留 planner 原文，
  右侧「打开课程」主按钮。
- 空状态用 `.tb-empty`，带「去做一遍最弱概念的练习」行动。

### 8.3 概念 `/concepts`

- 顶部：概念图卡片（见 8.9）。
- 表格：列改为 `概念 / 掌握度 / 等级 / 目标 / 到期 / 先修 / 课程`；
  **概念列显示标题**（`pack.concepts[cid].title`），ID 仅在 `title` 属性里；
  掌握度列 `tb-meter` + 数字；先修列显示标题（最多 2 个 + `等 N 个`）；
  `nowrap` 表头 + `min-width: 880px`。

### 8.4 复习 `/review` 与复习会话 `/review/session`

- 到期日：ISO → `M月D日`（新增 Jinja 过滤器 `tb_due`）。
- 行：练习题干摘要（`exercise.prompt` 截断 40 字）+ 概念标题 + 到期 + 「打开」。
- 空状态 `.tb-empty` + 「回到今日计划」。
- 会话页：顶部 `第 1 / 5 张` 进度条；卡片改为大卡、题干 17px；「下一张」为黑色主按钮。

### 8.5 进度 `/progress`

- Readiness 卡：数字 + 圆环 + 门控原因（折叠）。
- 掌握度表：概念标题 + meter + 等级 + 目标。
- 证据表：时间本地化为 `M月D日 HH:mm`，类型中文徽章，课程/练习列显示**标题与题干摘要**，
  结果列中文（`正确`/`部分正确`/`错误`/`已提交`）。
- 证据行数多时限高滚动（`max-height: 520px`）。

### 8.6 课程页 `/lesson/<id>`

- 面包屑改为 `模块 › 课程`，标题只出现一次（当前正文里 `M01 · 测试策略…` 与 h1 重复，
  改为模块名 + 序号 `第 3 课 / 共 7 课`）。
- 目标卡片（7 条约 4 行）。
- 正文按 6.3 排版。
- 练习卡 `.tb-exercise`：白底卡片 + 编号 + 题干 17px + 选项为整行可点（`label` 撑满、
  hover 高亮）+ 「提交」黑色主按钮 + 「提示」幽灵按钮。
- 反馈 `.tb-feedback`：成功/失败用 `-soft` 底 + 图标 + 文字。
- 追问区 `.tb-tutor`：改为卡片，消息气泡区分 user/assistant，来源徽章保留。
- 资源 `.tb-resources`：列表行 + trust 徽章。
- 上下课导航：两栏大按钮（左「上一课」右「下一课」），带课程名。

### 8.7 工作台类页面（面试/目标/求职）

- 统一 `tb-card` + `tb-section-title` + `tb-list-row` + `tb-table-wrap`。
- 求职列表加 `tb-tabs` 状态筛选。
- 表单统一 `tb-field` 上下布局，按钮区右对齐。

### 8.8 空状态

每个列表页都有 `.tb-empty`（图标 + 说明 + 主行动），替换现有裸 `<p>`。

### 8.9 概念图 `concept_graph.py`

- 节点：`rx=10`、白底 + 1px 边、**按等级着色左缘 3px 竖条**（而非整块填色）。
- 文字：标题最多 14 字（原 10），主行 12.5px `--tb-ink`，次行 `L0 · 0.00` 11px `--tb-muted`。
- 边长 30 → 36，边色 `#d4d4d8`，1.5px，**边在节点下方**（先画边）。
- 颜色从 CSS 变量取不到（SVG 内联于模板），因此在 SVG 内使用 `currentColor` +
  `class`，由 CSS 决定颜色 → 深色模式自动适配。
- 保留 `class="tb-graph-edge"`（`test_concept_graph.py` 断言计数）与 `data-concept`。

## 9. 国际化文案（消除内部标识符）

新增 `web/labels.py`：

```python
PLAN_TYPE_LABELS = {"review": "复习", "new": "新学", "weak": "补弱"}
OUTCOME_LABELS = {"correct": "正确", "partial": "部分正确",
                  "incorrect": "错误", "submitted": "已提交"}
LEVEL_LABELS = {"L0": "L0 · 未开始", ...}  # 表格内用短标签
TRUST_LABELS = {"A": "权威", "B": "可靠", "C": "参考", "D": "不采信"}
```

Jinja 全局注册为 `label(kind, value)`，模板内调用；未知值原样返回，
保证新枚举不会因为缺标签而白屏。

过滤器：`tb_date`（`M月D日`）、`tb_datetime`（`M月D日 HH:mm`）、
`tb_excerpt(n)`（截断 + 省略号）。

## 10. 图标方案

`web/templates/_icons.html`：

```jinja
{% macro icon(name, size=16, cls="") -%}
<svg class="tb-icon {{ cls }}" width="{{ size }}" height="{{ size }}" viewBox="0 0 24 24"
     fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"
     stroke-linejoin="round" aria-hidden="true" focusable="false">
  <use href="#i-{{ name }}"></use>
</svg>
{%- endmacro %}
```

`sprite` 由 `web/templates/_sprite.html` 提供，`base.html` 在 `<body>` 顶部 include 一次。
`sprite` 用 Lucide 原始 `path` 数据**手工内联**（约 20 个图标，逐个核对来源于 Lucide 仓库）。
`build.py` 内联同一份 sprite 片段到离线页，并在 `web/static/LICENSES.md` 记录许可证。

若 `<use href>` 在 `file://` 离线页有兼容问题，则退化为**直接内联路径宏**
（`icon()` 输出完整 `<path>`，不用 sprite）。**默认走退化为内联路径**，因为
`tb build` 是单文件、无 `<base>`，`<use href="#id">` 在同文档内可用，但为降低风险
直接内联。

## 11. 离线构建

`build.py` 的 `STANDALONE_TEMPLATE` 需要同步：

- 顶栏：品牌 + 返回链接（离线页无导航，改为「← 返回课程」到 `manifest.json` 无意义，
  改为纯品牌 + 课程标题）。
- `tb-export` 按钮改为 `tb-btn`。
- 新增 `.tb-lesson-shell` 容器保持正文宽度。
- 内联 `_sprite.html`（若采用内联路径则不需要）。
- 独立页不引入 `prefers-color-scheme` 之外的依赖。

## 12. 测试与验收

**自动化（新增）**

- `tests/test_labels.py`：标签映射全覆盖 + 未知值回退。
- `tests/test_web_ui.py` 扩充：
  - 首页含 `tb-kpi` 与 `tb-progress-ring`；
  - 概念页表头不换行（断言 `min-width` 存在于 CSS 或 class 存在）；
  - 首页不出现 `test-strategy-inputs` 这类裸 ID（用 sample 包的概念 ID 断言）；
  - `/review` 不出现 `T00:00:00` 形式的 ISO 串。
- `tests/test_concept_graph.py` 扩充：边在节点之前（字符串位置比较）。
- `tests/test_build.py` 扩充：离线页含新 token 与 `tb-lesson-main`。
- CSS 语法校验：用 Node 跑一个极简括号/`var()` 引用检查（无新依赖）。

**不回归**

- `test_web_ui.py` 现有 7 条 class 断言保持通过（`tb-card`、`tb-badge`、`tb-plan`、
  `tb-table-wrap`、`tb-callout`、`tb-main tb-lesson-main`、`tb-tutor tb-card`、
  `tb-resources tb-card`、`tb-nav`、`tb-skip-link`）。
- `test_career_*`、`test_interview_web.py` 的 class 断言：**保留这些 class 名**。
- 全量 `pytest` 无回归（基线以运行时实际数量为准）。

**人工验收（截图脚本）**

`ui-audit/shots.ps1` 在 1440 / 768 / 320 三档宽度、浅色与深色两种模式各拍一遍，
产出 `ui-audit/after/`，与 `ui-audit/before/` 对照。

## 13. 实施顺序

1. token 重写 + 基础排版 + 深色模式（不破结构）。
2. 组件层：card / kpi / ring / meter / badge / btn / callout / table / empty / field。
3. 顶栏 + 图标 + 布局容器。
4. 首页（KPI + 门控 + 今日 + 最弱 + 模块）。
5. 概念页（表头/标题/meter/先修/图）与 `concept_graph.py`。
6. 今日 / 复习 / 进度（标签过滤器 + 空状态）。
7. 课程页（正文排版 + 练习卡 + 追问 + 资源 + 上下课）。
8. 面试 / 目标 / 求职。
9. `build.py` 离线页同步。
10. 测试补强 + 三档截图对照。

## 14. 留给实施者的判断

- 圆环的具体尺寸与描边宽度（按 1440 实际观感微调）。
- 模块卡在 1024–1120px 区间是一栏还是两栏（按实测决定）。
- 图标清单最终取多少个（按页面实际需要，不追求齐全）。