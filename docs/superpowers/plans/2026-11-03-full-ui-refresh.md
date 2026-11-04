# TestBridge 全站视觉焕新 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 C（克制的现代产品）骨架 + B（编辑部式阅读）正文排版，重做 TestBridge 全站视觉，并把泄漏到界面的内部标识符换成自然语言。

**Architecture:** 纯 CSS 设计系统（无构建步骤、无 CDN）：一份 `web/static/tb.css` 提供 token 与组件类，14 个 Jinja 模板改用组件类并补结构化元素，`src/testbridge/icons.py` 提供内联 SVG 图标（`currentColor`），`web/labels.py` 提供枚举→中文标签与日期/截断过滤器。`tb build` 的离线单文件页内联同一份 CSS，因此同步更新其模板壳。

**Tech Stack:** Python 3.10+ / FastAPI / Jinja2 / 纯 CSS / 内联 SVG（无前端框架、无 npm）

**Spec:** `docs/superpowers/specs/2026-11-03-full-ui-refresh-design.md`

## Global Constraints

- **CSP 不变**：`default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'`。禁止内联 `<style>`/`<script>`、禁止任何外链（`tests/test_web.py:78` 断言此字符串）。
- **离线**：`tb build` 产物零外部请求；CSS 由 `build.py` 内联，图标以内联 SVG 出现。
- **不改业务语义**：路由、表单字段名、请求参数、`tb/1` 契约、判分/掌握度/调度/证据一律不动。只改模板、CSS、`concept_graph.py` 的 SVG 表现、`build.py` 的壳、以及新增的 `web/labels.py` + `src/testbridge/icons.py`。
- **保留精确 class 字符串**（现有测试用完整属性值做子串断言，写成 `class="tb-card tb-kpi"` 会失配）：
  - `class="tb-main tb-lesson-main"`（`test_web_ui.py:71`）
  - `class="tb-card"`、`class="tb-badge"`、`class="tb-table-wrap"`、`class="tb-plan"`、`class="tb-callout"`（`test_web_ui.py`、`test_web_p2.py`）
  - `class="tb-tutor tb-card"`、`class="tb-resources tb-card"`（`test_web_ui.py:72-73`）
  - `class="tb-app-form tb-form tb-card"`、`class="tb-btn tb-btn-primary"`、`class="tb-badge" data-status="applied"`（`test_career_applications_web.py`）
  - `class="tb-target-form tb-form tb-card"`、`class="tb-target-score tb-card"`（`test_career_web.py`）
  - `class="tb-interview-form tb-form tb-card"`、`class="tb-interview-session tb-card"`（`test_interview_web.py`）
  - `class="tb-skip-link"`、`class="tb-nav"`、`id="tb-main"`、`href="#tb-main"`、`href="/today" aria-current="page"`（`test_web_ui.py:29-36`）
  - `/progress` 面试类型单元格必须是 `<td><span class="tb-badge">面试</span></td>` 结构（`test_interview_web.py:269` 正则）
- **保留文案**：`Readiness`（`test_web_p2.py:29,47`）、`已按概念筛选：<id>`（`test_web_p2.py:86`）、`本概念 N 条 / 全局 M 条`（:86）、`掌握度偏低`（:39）、`data-status="weak"`（:40）、`<th>概念</th>`/`<th>等级</th>`/`<th>目标</th>`/`<th>类型</th>`（:63-65、:135）、`今天没有到期卡`（`test_review_session.py:36`）、`共 N 张`（:46）、`N 张卡对应的练习已不存在`（:85）、`data-exercise-id=`/`data-lesson-id=`（:47,59）。
- **`/progress?concept=<id>` 必须仍包含该 id 原文**（`test_web_p2.py:72`）。
- **基线测试**：改动前 `pytest -q` = **639 passed**。收尾必须仍是 639 passed 或更多，零失败。
- 中文不使用衬线字体（本机无 Noto Serif SC，SimSun 小字号发虚）；衬线仅用于拉丁字母与数字。
- 用户可见文案用中文；代码标识符与注释用英文。

## Review Focus

1. **空数据页面**（无证据、无到期卡、无投递、无题库）：`/`、`/today`、`/review`、`/progress`、`/applications`、`/interview` 在全新数据库下必须渲染空状态而不是空白或 `None` 字样。
2. **长内容不撑破布局**：21 概念的 `/concepts`、200 条证据的 `/progress`、超长概念标题（`Flakiness、基线与趋势分析`）与超长题干，在 320px 下不得横向滚动页面（表格自身滚动除外）。
3. **深色模式下的语义色**：`correct/incorrect` 反馈、徽章、概念图节点在 `prefers-color-scheme: dark` 下仍需与背景有 3:1 以上对比，不能出现白底黑字卡片。
4. **`tb build` 离线页**：单文件 HTML 在断网下打开，样式与 Web 一致，练习提交与导出按钮可用。
5. **未知枚举值**：`label()` 遇到未登记的值（如未来新增的 `plan.type`）必须原样返回，不能抛异常或渲染空白。

---

### Task 1: 设计 token 与基础排版

**Files:**
- Modify: `web/static/tb.css:1-883`（整体重写 token 段与基础排版段，组件段留待后续任务逐步替换）

**Interfaces:**
- Produces: CSS 变量 `--tb-bg`、`--tb-bg-elevated`、`--tb-bg-sunken`、`--tb-ink`、`--tb-ink-2`、`--tb-muted`、`--tb-faint`、`--tb-line`、`--tb-line-soft`、`--tb-accent`、`--tb-accent-ink`、`--tb-accent-soft`、`--tb-success/warning/danger`（各带 `-soft`）、`--tb-radius-sm/md/lg/pill`、`--tb-space-1..12`、`--tb-text-xs..3xl`、`--tb-font-sans/serif/mono`、`--tb-shadow-sm/md`。后续任务只引用这些变量，不写死颜色。

- [ ] **Step 1: 写 CSS 校验测试**

创建 `tests/test_css_tokens.py`：

```python
"""Structural checks on the single shared stylesheet.

These do not try to parse CSS. They pin the handful of invariants that the
redesign depends on: every token a template references exists, dark mode
overrides every surface token, and the table fix that stopped headers from
wrapping is present.
"""

from pathlib import Path
import re

CSS = (Path(__file__).parents[1] / "web" / "static" / "tb.css").read_text(encoding="utf-8")


def test_dark_mode_overrides_every_surface_token() -> None:
    dark = CSS.split("@media (prefers-color-scheme: dark)", 1)[1]
    for token in ("--tb-bg", "--tb-bg-elevated", "--tb-bg-sunken", "--tb-ink", "--tb-line"):
        assert f"{token}:" in dark.split("}", 1)[0]


def test_every_var_reference_is_defined() -> None:
    defined = set(re.findall(r"(--tb-[\w-]+)\s*:", CSS))
    used = set(re.findall(r"var\((--tb-[\w-]+)", CSS))
    missing = {name for name in used if name not in defined}
    assert not missing, f"undefined custom properties: {sorted(missing)}"


def test_table_headers_never_wrap() -> None:
    assert re.search(r"th,\s*td[^{]*\{[^}]*white-space:\s*nowrap", CSS)
    assert re.search(r"\.tb-table-wrap table\s*\{[^}]*min-width:\s*\d+px", CSS)


def test_no_external_resource_reference() -> None:
    assert "http://" not in CSS
    assert "https://" not in CSS
    assert "@import" not in CSS
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_css_tokens.py -q`
Expected: FAIL（`--tb-bg-elevated` 未定义、表头无 `nowrap`）

- [ ] **Step 3: 重写 `tb.css` 的 token 段与基础排版段**

替换 `:root` / 深色模式 / `body` / 标题 / 表格段，按 spec §5 与 §6.3 的数值原样写入。
保留文件末尾的 `:focus-visible`、`prefers-reduced-motion`、响应式段。
旧别名 `--ink`/`--muted`/`--line`/`--accent`/`--bg` 继续指向新 token，
避免尚未替换的旧规则失效。

关键必写规则：

```css
th, td { white-space: nowrap; }          /* 表头不再折成竖排 */
.tb-lesson th, .tb-lesson td { white-space: normal; }  /* 正文表格允许换行 */
.tb-table-wrap { overflow-x: auto; }
.tb-table-wrap table { min-width: 640px; }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/Scripts/python.exe -m pytest tests/test_css_tokens.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 全量回归**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: 643 passed（639 + 4）

- [ ] **Step 6: Commit**

```bash
git add web/static/tb.css tests/test_css_tokens.py
git commit -m "feat(ui): rewrite design tokens, dark mode, and table layout"
```

---

### Task 2: 标签与日期过滤器

**Files:**
- Create: `web/labels.py`
- Modify: `web/app.py:125`（`templates` 创建处之后注册过滤器与全局）
- Test: `tests/test_labels.py`

**Interfaces:**
- Produces:
  - `plan_type_label(value: str) -> str`
  - `outcome_label(value: str | None) -> str`
  - `level_label(value: str) -> str`
  - `trust_label(value: str) -> str`
  - `format_date(value: str | None) -> str` → `M月D日`，解析失败返回原值
  - `format_datetime(value: str | None) -> str` → `M月D日 HH:mm`，解析失败返回原值
  - `excerpt(value: str | None, limit: int = 40) -> str`
  - `register(templates) -> None`：注册过滤器 `tb_date`、`tb_datetime`、`tb_excerpt`，
    全局 `label(kind, value)`
- 后续任务在模板中使用 `{{ "review" | plan_type }}` 形式改为 `{{ item.type | tb_label("plan_type") }}`。
  为简化，统一提供 `tb_label(kind, value)` 过滤器。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_labels.py`：

```python
from datetime import datetime, timezone

from web.labels import (
    excerpt, format_date, format_datetime, label, level_label,
    outcome_label, plan_type_label, trust_label,
)


def test_plan_types_are_chinese() -> None:
    assert plan_type_label("review") == "复习"
    assert plan_type_label("new") == "新学"
    assert plan_type_label("weak") == "补弱"


def test_unknown_values_pass_through_untouched() -> None:
    # A new enum value must never blank the page or raise.
    assert plan_type_label("spaced_repetition") == "spaced_repetition"
    assert outcome_label(None) == ""
    assert label("no_such_kind", "x") == "x"


def test_outcomes_levels_and_trust() -> None:
    assert outcome_label("correct") == "正确"
    assert outcome_label("partial") == "部分正确"
    assert outcome_label("submitted") == "已提交"
    assert level_label("L3") == "L3"
    assert trust_label("A") == "A"


def test_iso_date_becomes_local_short_form() -> None:
    assert format_date("2020-01-02T00:00:00+00:00") == "1月2日"
    assert format_datetime("2020-01-02T03:04:00+00:00") == "1月2日 11:04"
    assert format_date("not-a-date") == "not-a-date"
    assert format_date(None) == ""


def test_excerpt_truncates_on_character_boundary() -> None:
    assert excerpt("短题干", 40) == "短题干"
    long = "一" * 50
    assert excerpt(long, 40) == "一" * 40 + "…"
    assert excerpt(None) == ""
```

> **注意**：`format_datetime` 必须把 UTC 转成本地时区（`Asia/Shanghai`），
> 因此 03:04 UTC → 11:04。用 `datetime.now().astimezone().tzinfo` 取本地时区，
> 不要硬编码 `+8`。

- [ ] **Step 2: 运行确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_labels.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'web.labels'`

- [ ] **Step 3: 实现 `web/labels.py`**

映射表用模块级 dict 常量（`PLAN_TYPES`、`OUTCOMES`、`LEVELS`、`TRUSTS`），
查不到时 `return value`。日期函数用 `datetime.fromisoformat`，
`astimezone()` 后格式化；捕获 `ValueError` 返回原值。

- [ ] **Step 4: 在 `web/app.py` 注册**

在 `templates = Jinja2Templates(...)` 之后加：

```python
from web.labels import register as register_labels

register_labels(templates)
```

- [ ] **Step 5: 运行测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_labels.py -q`
Expected: PASS（5 passed）

- [ ] **Step 6: Commit**

```bash
git add web/labels.py web/app.py tests/test_labels.py
git commit -m "feat(ui): add Chinese labels and date filters for templates"
```

---

### Task 3: 图标接入

**Files:**
- Create: `web/templates/_icons.html`（Jinja 宏 `icon(name, size=16, cls="")`）
- Modify: `web/app.py:125`（注册全局 `icon`）
- Test: `tests/test_icons.py`

**Interfaces:**
- Consumes: `src/testbridge/icons.py::icon_markup(name, size, cls)`（已存在，28 个图标）
- Produces: 模板内可用 `{{ icon("clock", 14) }}`；`icon_markup` 对未知名返回 `""`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_icons.py`：

```python
from testbridge.icons import ICONS, icon_markup


def test_all_icons_render_and_are_self_contained() -> None:
    for name in ICONS:
        markup = icon_markup(name)
        assert markup.startswith("<svg")
        assert 'aria-hidden="true"' in markup
        assert "currentColor" in markup
        assert "http" not in markup


def test_unknown_icon_degrades_to_nothing() -> None:
    assert icon_markup("definitely-not-an-icon") == ""


def test_icons_have_no_script_or_style_attributes() -> None:
    for name in ICONS:
        markup = icon_markup(name)
        assert "<script" not in markup
        assert "style=" not in markup
        assert "onload" not in markup


def test_icon_appears_on_pages(tmp_path) -> None:
    from fastapi.testclient import TestClient
    from pathlib import Path
    from web.app import create_app

    sample = Path(__file__).parents[1] / "tests" / "fixtures" / "packs" / "sample-sensors"
    text = TestClient(create_app(sample, tmp_path / "i.db")).get("/").text
    assert 'class="tb-icon' in text
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_icons.py -q`
Expected: FAIL — 最后一个测试找不到 `tb-icon`（页面尚未用图标）

- [ ] **Step 3: 创建宏并在 app 注册**

`web/templates/_icons.html`：

```jinja
{% macro icon(name, size=16, cls="") -%}
{{ icon_svg(name, size, cls) | safe }}
{%- endmacro %}
```

`web/app.py` 注册：

```python
from testbridge.icons import icon_markup

templates.env.globals["icon_svg"] = icon_markup
```

- [ ] **Step 4: 在 base.html 顶栏用上图标（首个使用点）**

Task 4 会重写顶栏；本步骤只在品牌左侧加一个 `icon("graduation-cap", 15)`，
让 `tb-icon` 类出现在页面上，保证测试通过。

- [ ] **Step 5: 运行测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_icons.py tests/test_web_ui.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/templates/_icons.html web/app.py web/templates/base.html tests/test_icons.py
git commit -m "feat(ui): wire vendored Lucide icons into templates"
```

---

### Task 4: 顶栏与布局容器

**Files:**
- Modify: `web/templates/base.html`（整体重写 `header` 与 `main`）
- Modify: `web/static/tb.css`（`.tb-top` / `.tb-nav` / `.tb-main` 段）

**Interfaces:**
- Consumes: `icon()` 全局（Task 3）
- Produces: 模板骨架 —— `header.tb-top > a.tb-brand + nav.tb-nav`，`main#tb-main.tb-main`
  （课程页追加 `tb-lesson-main`，由子模板 `main_class` block 控制，保持不变）

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_web_ui.py`：

```python
def test_nav_groups_keep_single_current_page_marker(tmp_path: Path) -> None:
    text = client(tmp_path).get("/concepts").text
    assert text.count('aria-current="page"') == 1
    # 分组容器存在，且导航项仍是链接（≤760px 横向滚动后依然可点）
    assert 'class="tb-nav"' in text
    assert text.count('<a href="/') >= 7
```

- [ ] **Step 2: 运行确认失败（或通过——若通过直接进 Step 3）**

Run: `.venv/Scripts/python.exe -m pytest tests/test_web_ui.py -q`

- [ ] **Step 3: 重写 `base.html`**

结构：

```jinja
<header class="tb-top">
  <a href="/" class="tb-brand">{{ icon("graduation-cap", 16) }}<span>TestBridge</span></a>
  <nav class="tb-nav" aria-label="主导航">…8 项…</nav>
</header>
<main class="tb-main {% block main_class %}{% endblock %}" id="tb-main">…</main>
```

硬性保留：`class="tb-skip-link"`、`href="#tb-main"`、`id="tb-main"`、
`class="tb-nav"`、`aria-current="page"` 唯一性、`class="tb-main tb-lesson-main"` 组合
（由 `main_class` block 产出，写死 `tb-main` + block，中间单空格）。

- [ ] **Step 4: CSS：sticky 半透明顶栏 + 窄屏横向滚动导航**

```css
@media (max-width: 760px) {
  .tb-nav { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; }
  .tb-nav::-webkit-scrollbar { display: none; }
}
```

- [ ] **Step 5: 运行测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_web_ui.py -q`
Expected: PASS（8 passed）

- [ ] **Step 6: Commit**

```bash
git add web/templates/base.html web/static/tb.css tests/test_web_ui.py
git commit -m "feat(ui): rebuild header, nav grouping, and content container"
```

---

### Task 5: 首页仪表盘

**Files:**
- Modify: `web/templates/dashboard.html`（整体重写）
- Modify: `web/app.py:170-190`（`dashboard` 视图补充 `concept_titles`、`mastered_count`、`module_stats`）
- Modify: `web/static/tb.css`（新增 `.tb-kpi`、`.tb-progress-ring`、`.tb-meter`、`.tb-section-title`、`.tb-list-row`）
- Test: `tests/test_web_ui.py`

**Interfaces:**
- Consumes: `readiness: ReadinessView`、`plan: DailyPlan`、`weakest: list[MasteryView]`、`due_count: int`
- Produces: 视图新增键 `concept_titles: dict[str, str]`、`mastered_count: int`、
  `concept_total: int`、`module_rows: list[dict]`（每项含 `module`、`lessons`、`done`）

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_web_ui.py`：

```python
def test_dashboard_shows_kpis_and_hides_raw_concept_ids(tmp_path: Path) -> None:
    text = client(tmp_path).get("/").text
    assert "tb-kpi" in text
    # 门控不再把 13 条 "xxx 估计 L0，目标 L3" 直接铺开
    assert "估计 L0，目标 L3" not in text
    # 最弱概念显示标题而不是裸 ID
    assert "sensor-time-sync" not in text
    assert text.count('class="tb-card"') >= 1
    assert 'class="tb-badge"' in text


def test_dashboard_exposes_progress_ring(tmp_path: Path) -> None:
    text = client(tmp_path).get("/").text
    assert "tb-progress-ring" in text
    assert "Readiness" in text
```

> **注意**：`sample-sensors` 包的概念 ID 是 `sensor-time-sync` 等；
> 断言它不出现，等于断言页面只用标题。

- [ ] **Step 2: 运行确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_web_ui.py -q`
Expected: FAIL — `tb-kpi` 不存在

- [ ] **Step 3: 扩展 `dashboard` 视图**

在 `web/app.py` 的 `dashboard()` 中构造：

```python
concept_titles = {cid: item.title for cid, item in pack.concepts.items()}
mastered_count = sum(1 for view in views.values()
                     if LEVEL_ORDER[view.level] >= LEVEL_ORDER[pack.concepts[view.concept_id].target_level])
```

（`LEVEL_ORDER` 从 `testbridge.readiness` 导入。）

`module_rows` 每项：`{"module": module, "lessons": [...], "done": <该模块已达目标等级的概念数>}`
—— `done` 用该模块概念里 `level >= target_level` 的数量，不做课程完成度伪造。

- [ ] **Step 4: 重写 `dashboard.html`**

结构（顺序固定）：

1. `<h1>{{ pack.meta.title }}</h1>` + `.tb-meta` 描述 + `内容包 · {{ pack.meta.id }}` 小字
2. KPI 行：Readiness 大卡（`.tb-kpi tb-kpi-main`，含 `tb-progress-ring` SVG，
   `stroke-dashoffset` 由 `readiness.total` 计算；圆环半径 44、周长 276、
   offset = `276 - 276 * total`）+ 到期复习 + 今日计划项/分钟 + 已掌握 `n / total`
3. 门控：`<p class="tb-callout" data-tone="warn">`，文案
   `门控生效：{{ readiness.gate_reasons|length }} 个 P0 概念未达目标等级，readiness 上限 0.70`
   + `<details><summary>查看具体概念</summary><ul>…</ul></details>`
4. 两栏：今日计划（前 2 项，`.tb-list-row`，主按钮 `<a class="tb-btn tb-btn-primary">开始</a>`）
   ／最弱概念（3 行，`.tb-meter` 宽度 = `estimate * 100%`，右侧 `L0 · 目标 L3` 用 `concept_titles`）
5. 模块区：每模块一个 `class="tb-card"`（**精确值，不加其他类**），卡内
   `h2` + `.tb-meta` `{{ row.done }} / {{ row.lessons|length }}` + 课程行

- [ ] **Step 5: 补组件 CSS**

`.tb-kpi`、`.tb-kpi-main`、`.tb-progress-ring`、`.tb-meter`、`.tb-meter > i`、
`.tb-section-title`、`.tb-list-row`、`.tb-stat-row`。深色模式走 token，不写死颜色。

- [ ] **Step 6: 运行测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_web_ui.py tests/test_web_p2.py -q`
Expected: PASS（含 `Readiness` 与 `href="/today"` 旧断言）

- [ ] **Step 7: Commit**

```bash
git add web/templates/dashboard.html web/app.py web/static/tb.css tests/test_web_ui.py
git commit -m "feat(ui): rebuild dashboard with KPI cards, ring, and module progress"
```

---

### Task 6: 概念页与先修图

**Files:**
- Modify: `web/templates/concepts.html`
- Modify: `src/testbridge/concept_graph.py:58-121`（`prerequisite_svg` 表现层）
- Modify: `web/app.py:237-256`（传 `concept_titles`、`prereq_titles` 给模板）
- Test: `tests/test_concept_graph.py`、`tests/test_web_p2.py`

**Interfaces:**
- Consumes: `prerequisite_svg(pack, views)` 保持签名与 `class="tb-graph"`、
  `class="tb-graph-edge"`、`data-concept="<id>"`（测试已断言）
- Produces: SVG 节点改为「白底 + 等级色左缘竖条」，文字仍由 `concept.title` 截断
  （`TITLE_LIMIT` 10 → 14）

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_concept_graph.py`：

```python
def test_edges_are_drawn_before_nodes_so_lines_stay_behind() -> None:
    svg = prerequisite_svg(PACK)
    first_edge = svg.index('class="tb-graph-edge"')
    first_node = svg.index("data-concept=")
    assert first_edge < first_node


def test_nodes_use_css_classes_not_hardcoded_dark_text() -> None:
    svg = prerequisite_svg(PACK)
    assert 'class="tb-graph-node"' in svg
    # 深色模式适配：标题不再写死 #111827
    assert "#111827" not in svg
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_concept_graph.py -q`
Expected: FAIL — 边在节点之后 / 无 `tb-graph-node`

- [ ] **Step 3: 重写 `prerequisite_svg`**

保持几何常量与 `graph_levels` 算法不变；只改：先 `edges` 后 `nodes`（已有顺序即是），
节点 `<g class="tb-graph-node" data-concept="…">` + 白底 rect + 左侧 3px 等级色 rect +
`<text class="tb-graph-label">` / `<text class="tb-graph-sub">`，不带 `fill` 属性。
边 `<line class="tb-graph-edge">` 不带 `stroke` 属性，颜色由 CSS 给。
`LEVEL_FILL` 改为 `LEVEL_BAR`（等级→左缘颜色），键仍为 L0–L4。

- [ ] **Step 4: CSS 补图样式**

`.tb-graph-node rect { fill: var(--tb-bg-elevated); stroke: var(--tb-line); }`
`.tb-graph-label { fill: var(--tb-ink); font-size: 12.5px; }`
`.tb-graph-sub { fill: var(--tb-muted); font-size: 11px; }`
`.tb-graph-edge { stroke: var(--tb-line); stroke-width: 1.5; }`

- [ ] **Step 5: 重写 `concepts.html`**

表格列保持 `概念 / 掌握度 / 等级 / 目标 / 到期 / 先修 / 课程`；
概念列显示 `concept_titles[cid]`，链接仍为 `/progress?concept=<id>`（保留 ID 原文），
并给该链接加 `title="{{ concept_id }}"`；
掌握度列 `.tb-meter` + 数字；先修列显示标题（最多 2 个，其余 `等 N 个`）；
表格外层 `class="tb-table-wrap"`，表内 `<th>` 文案保持不变。

- [ ] **Step 6: 运行测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_concept_graph.py tests/test_web_p2.py -q`
Expected: PASS（含 `class="tb-graph"`、`data-concept=`、`href="/progress?concept=sensor-time-sync"`、`<th>概念</th>` 旧断言）

- [ ] **Step 7: Commit**

```bash
git add web/templates/concepts.html src/testbridge/concept_graph.py web/app.py web/static/tb.css tests/test_concept_graph.py
git commit -m "feat(ui): redesign concepts page and prerequisite graph"
```

---

### Task 7: 今日 / 复习 / 复习会话

**Files:**
- Modify: `web/templates/today.html`、`web/templates/review.html`、`web/templates/review_session.html`
- Modify: `web/static/tb.css`（`.tb-empty`、`.tb-tabs`、会话进度条）
- Modify: `tests/test_web_p2.py:116-117`（日期断言改为人类可读格式）

**Interfaces:**
- Consumes: `tb_label`、`tb_date`、`tb_excerpt` 过滤器（Task 2）
- Produces: 三页均使用 `.tb-empty` 空状态；计划项类型徽章为中文但保留
  `data-status="review|new|weak"`（`test_web_p2.py:40` 断言 `data-status="weak"`）

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_web_p2.py`：

```python
def test_today_uses_chinese_plan_labels(tmp_path: Path) -> None:
    c = client(tmp_path)
    c.post("/api/evidence", json={
        "lesson_id": "L-SYNC-001", "exercise_id": "EX-SYNC-001", "response": "wrong",
    })
    text = c.get("/today").text
    assert "补弱" in text
    assert ">weak<" not in text


def test_review_shows_human_readable_due_date(tmp_path: Path) -> None:
    app = client(tmp_path)
    from testbridge.learning.store import ReviewState
    app.app.state.learning.store.upsert_review(ReviewState(
        learner_id="local", exercise_id="EX-SYNC-001",
        concept_ids=["sensor-time-sync"], due="2020-01-02T00:00:00+00:00",
        stability=1.0, difficulty=5.0, reps=1, lapses=0, state="Review",
        last_review=None,
        card_json={"card_id": 1, "state": 2, "step": 0, "stability": 1.0,
                   "difficulty": 5.0, "due": "2020-01-02T00:00:00+00:00",
                   "last_review": None},
    ))
    text = app.get("/review").text
    assert "1月2日" in text
    assert "T00:00:00" not in text
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_web_p2.py -q`
Expected: FAIL — 出现 `>weak<`、`T00:00:00`

- [ ] **Step 3: 改 `today.html`**

顶部 `.tb-stat-row`（预算/已排/项数）；列表项改为 `.tb-list-row`：
`<span class="tb-badge" data-status="{{ item.type }}">{{ item.type | tb_label("plan_type") }}</span>`
+ 标题（`item.lesson_id` 对应课程标题，需在视图补 `lesson_titles`）
+ 理由 + `{{ item.estimated_minutes }} 分钟` + 主按钮「打开课程」。
空态用 `.tb-empty`。

> 需要在 `web/app.py` 的 `today_page` 里补 `lesson_titles =
> {lid: lesson.manifest.title for lid, lesson in pack.lessons.items()}`。

- [ ] **Step 4: 改 `review.html`**

到期列 `{{ row.review.due | tb_date }}`；练习列 `{{ row.review.exercise_id }}`
**保留**（作为可定位标识，`test_web_p2.py:116` 断言），另加题干摘要列
（视图补 `exercise_prompts`）。保留 `href="/review/session"`。

- [ ] **Step 5: 改 `review_session.html`**

顶部 `第 {{ loop }} / {{ cards|length }} 张` 进度条；卡片 `class="tb-card"`；
「下一张」用 `tb-btn tb-btn-primary`。保留 `data-exercise-id`、`data-lesson-id`、
`共 N 张`、`今天没有到期卡`、`N 张卡对应的练习已不存在` 文案。

- [ ] **Step 6: 更新过期的日期断言**

把 `tests/test_web_p2.py` 中：

```python
assert "EX-SYNC-001" in text
assert "2020-01-01" in text
```

改为：

```python
assert "EX-SYNC-001" in text
assert "1月1日" in text          # 到期日已本地化
```

这是设计决定的直接结果（spec §8.4），不是放宽覆盖：行内容仍被断言。

- [ ] **Step 7: 运行测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_web_p2.py tests/test_review_session.py tests/test_web_ui.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add web/templates/today.html web/templates/review.html web/templates/review_session.html web/app.py web/static/tb.css tests/test_web_p2.py
git commit -m "feat(ui): humanize today and review pages"
```

---

### Task 8: 进度页

**Files:**
- Modify: `web/templates/progress.html`
- Modify: `web/app.py:212-228`（补 `concept_titles`、`lesson_titles`、`exercise_prompts`）

**Interfaces:**
- Consumes: `tb_date`/`tb_datetime`/`tb_label`/`tb_excerpt`
- Produces: 证据类型单元格**结构不变**：`<td><span class="tb-badge">面试</span></td>`
  （`test_interview_web.py:269` 正则依赖）

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_web_p2.py`：

```python
def test_progress_evidence_table_is_humanized(tmp_path: Path) -> None:
    c = client(tmp_path)
    c.post("/api/evidence", json={
        "lesson_id": "L-SYNC-001", "exercise_id": "EX-SYNC-001", "response": "a",
    })
    text = c.get("/progress").text
    assert "T00:00:00" not in text.split("掌握度", 1)[1]
    assert "已提交" in text or "正确" in text or "错误" in text
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_web_p2.py::test_progress_evidence_table_is_humanized -q`

- [ ] **Step 3: 改 `progress.html`**

Readiness 卡保留 `Readiness` 字样与 `.tb-card`；门控原因改成 `<details>`；
掌握度表保留 `<th>概念</th>/<th>等级</th>/<th>目标</th>` 原文；
概念列显示标题、链接带 `?concept=<id>`；
证据表列 `时间/类型/课程/练习/结果/详情`：时间 `tb_datetime`，类型徽章**结构与文案不变**，
结果用 `outcome_label`，课程与练习显示标题/题干摘要（`title` 属性放原 ID）。

- [ ] **Step 4: 运行测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_web_p2.py tests/test_interview_web.py -q`
Expected: PASS（含 `<td><span class="tb-badge">面试</span></td>` 正则与
`本概念 N 条 / 全局 M 条`）

- [ ] **Step 5: Commit**

```bash
git add web/templates/progress.html web/app.py tests/test_web_p2.py
git commit -m "feat(ui): humanize progress page and evidence table"
```

---

### Task 9: 课程页阅读排版

**Files:**
- Modify: `web/templates/lesson.html`
- Modify: `web/static/tb.css`（`.tb-lesson-main`、`.tb-lesson`、`.tb-exercise`、`.tb-tutor`、`.tb-resources`、`.tb-pager`）
- Modify: `web/app.py:192-210`（补 `lesson_position`、`module_title`）

**Interfaces:**
- Produces: `lesson_position = {"index": int, "total": int}`；模板仍输出
  `class="tb-tutor tb-card"`、`class="tb-resources tb-card"`、
  `class="tb-main tb-lesson-main"`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_web_ui.py`：

```python
def test_lesson_reading_typography_and_position(tmp_path: Path) -> None:
    text = client(tmp_path).get("/lesson/L-SYNC-001").text
    assert "第 1 课" in text or "1 /" in text
    assert '<ul class="tb-objectives">' in text
    assert text.count("<h1>") == 1        # 标题不再重复
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_web_ui.py::test_lesson_reading_typography_and_position -q`
Expected: FAIL — h1 出现两次（正文里还有一个）

> **实现要点**：正文 HTML 由内容包提供，可能自带 `<h1>`。**不要**改内容或净化器；
> 在 `lesson.html` 里用 CSS 处理：`.tb-lesson h1 { display: none; }`。
> 这也解释了为什么测试断言 `text.count("<h1>") == 1` 需要改为统计**可见**标题——
> 若正文确有 h1，改为断言 `text.count('<h1>{{ view.lesson.manifest.title }}</h1>') == 1`
> 并在 CSS 里隐藏 `.tb-lesson h1`。

- [ ] **Step 3: 改 `lesson.html`**

面包屑 `{{ module_title }} › 第 {{ lesson_position.index }} 课 / 共 {{ lesson_position.total }} 课`；
h1 只出现一次；目标卡 `class="tb-objectives"`（保持标签）+
`<h2>本课目标</h2>`；正文 `<article class="tb-lesson">`；
练习/追问/资源/上下课按 spec §8.6。

- [ ] **Step 4: CSS 阅读排版**

`.tb-main.tb-lesson-main { max-width: 46rem; }`
`.tb-lesson { font-size: 16.5px; line-height: 1.85; }`
`.tb-lesson h2 { font-size: 20px; margin: 40px 0 12px; padding-left: 12px; border-left: 3px solid var(--tb-accent); }`
`.tb-lesson pre { background: #1a1a1f; color: #e8e8ea; }`（浅色模式也用深底）
`.tb-exercise label { display: flex; padding: 10px 12px; border: 1px solid var(--tb-line); border-radius: 8px; }`

- [ ] **Step 5: 运行测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_web_ui.py tests/test_web.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/templates/lesson.html web/app.py web/static/tb.css tests/test_web_ui.py
git commit -m "feat(ui): lesson reading typography, exercise cards, and pager"
```

---

### Task 10: 面试 / 目标 / 求职

**Files:**
- Modify: `web/templates/interview_start.html`、`interview_session.html`、`interview_summary.html`、`target.html`、`target_review.html`、`applications.html`、`application_detail.html`
- Modify: `web/static/tb.css`（`.tb-tabs`、`.tb-field`、表格）

**Interfaces:**
- Consumes: Task 2 过滤器、Task 3 图标
- Produces: 七个模板保持 Global Constraints 列出的**精确 class 字符串**

- [ ] **Step 1: 运行现有断言作为护栏（先确认基线）**

Run: `.venv/Scripts/python.exe -m pytest tests/test_interview_web.py tests/test_career_web.py tests/test_career_applications_web.py -q`
Expected: PASS（记录数量）

- [ ] **Step 2: 改模板**

统一：`h1` 下加 `.tb-meta` 摘要；表格包 `.tb-table-wrap`；表单字段用 `.tb-field`；
按钮区 `display:flex; gap:8px; justify-content:flex-end`；
求职状态筛选改为 `.tb-tabs`（保留 `<a href="/applications?status=…">` 链接）；
空状态用 `.tb-empty`。

**不要动**表单 `name` 属性、`action`、`method`、hidden input。

- [ ] **Step 3: 运行护栏测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_interview_web.py tests/test_career_web.py tests/test_career_applications_web.py -q`
Expected: PASS，数量与 Step 1 相同

- [ ] **Step 4: Commit**

```bash
git add web/templates/interview_start.html web/templates/interview_session.html web/templates/interview_summary.html web/templates/target.html web/templates/target_review.html web/templates/applications.html web/templates/application_detail.html web/static/tb.css
git commit -m "feat(ui): unify interview, target, and applications pages"
```

---

### Task 11: 离线构建同步

**Files:**
- Modify: `src/testbridge/build.py:14-31`（`STANDALONE_TEMPLATE`）
- Test: `tests/test_build.py`

**Interfaces:**
- Produces: 单文件 HTML 内联新 CSS；导出按钮为 `.tb-btn`；
  顶栏为纯品牌 + 课程标题（无导航，离线页无路由）

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_build.py`：

```python
def test_standalone_page_inlines_new_design_tokens(tmp_path: Path) -> None:
    html_text = build_pack(FIXTURE, tmp_path)[0].read_text(encoding="utf-8")
    assert "--tb-bg-elevated" in html_text
    assert "tb-btn" in html_text
    assert "http://" not in html_text.split("</style>", 1)[1]


def test_standalone_page_has_no_external_requests(tmp_path: Path) -> None:
    html_text = build_pack(FIXTURE, tmp_path)[0].read_text(encoding="utf-8")
    assert "<link" not in html_text
    assert "@import" not in html_text
    assert "<script src=" not in html_text
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_build.py -q`

- [ ] **Step 3: 改 `STANDALONE_TEMPLATE`**

加 `header.tb-top`（品牌 + 课程标题）、包一层保持阅读宽度的结构、
导出按钮改 `class="tb-btn"`。**保持** `<main class="tb-main tb-lesson-main">` 原样
（`test_build.py:27` 断言）。

- [ ] **Step 4: 运行测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_build.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/build.py tests/test_build.py
git commit -m "feat(build): sync offline lesson shell with the new design"
```

---

### Task 12: 三档截图对照与收尾

**Files:**
- Create: `ui-audit/after/`（截图产物，gitignore）
- Modify: `.gitignore`（追加 `ui-audit/`）

**Interfaces:**
- Consumes: 任务 1–11 的全部产出

- [ ] **Step 1: 重启本地服务**

现有 `8000` 端口进程是旧代码；结束它并用新代码重启：

```bash
# 确认是 tb serve 而非其他项目
.venv\Scripts\python.exe -m testbridge.cli serve content-packs/robot-quality-system --port 8000
```

- [ ] **Step 2: 拍三档截图**

```powershell
& .\ui-audit\shots.ps1 -Out ui-audit\after -Width 1440 -Height 1600
& .\ui-audit\shots.ps1 -Out ui-audit\after-768 -Width 768 -Height 1600
& .\ui-audit\shots.ps1 -Out ui-audit\after-320 -Width 320 -Height 1600
```

- [ ] **Step 3: 人眼看图**

逐张对照 `ui-audit/before/`。验收点：首页三秒可读、概念表头不竖排、
320px 无横向滚动、课程页正文行宽适中。

- [ ] **Step 4: 深色模式抽查**

用 Edge `--force-dark-mode` 重拍首页与课程页，确认卡片不倒色。

- [ ] **Step 5: 全量测试**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: **≥ 639 passed，0 failed**

- [ ] **Step 6: 三个内容包仍可构建**

```bash
.venv\Scripts\python.exe -m testbridge.cli validate content-packs/robot-quality-system
.venv\Scripts\python.exe -m testbridge.cli validate content-packs/ros2-qos
.venv\Scripts\python.exe -m testbridge.cli build content-packs/robot-quality-system --out dist
```

Expected: `0 error(s), 0 warning(s)`；build 成功

- [ ] **Step 7: 更新 ROADMAP**

在 `docs/ROADMAP.md` 末尾追加一节「2026-11-03 全站视觉焕新 — 已完成」，
记录范围、验证数字与截图位置。

- [ ] **Step 8: Commit**

```bash
git add .gitignore docs/ROADMAP.md
git commit -m "docs: record full UI refresh and verification results"
```

---

## Self-Review

**1. Spec coverage**

| Spec 章节 | 任务 |
|---|---|
| §5 token | 1 |
| §6.1 顶栏 | 4 |
| §6.2 容器 | 1、4 |
| §6.3 课程正文 | 9 |
| §7 组件 | 1、5、9、10 |
| §8.1 首页 | 5 |
| §8.2 今日 | 7 |
| §8.3 概念 | 6 |
| §8.4 复习 | 7 |
| §8.5 进度 | 8 |
| §8.6 课程页 | 9 |
| §8.7 工作台 | 10 |
| §8.8 空状态 | 5、7、8、10 |
| §8.9 概念图 | 6 |
| §9 文案 | 2 |
| §10 图标 | 3 |
| §11 离线 | 11 |
| §12 测试与验收 | 各任务 + 12 |

**2. Step scan** — 每步一个可验证动作；无 "TBD"、无 "add appropriate validation"。

**3. Type consistency** — `icon_markup(name, size, cls)`、`tb_label`/`tb_date`/`tb_datetime`/
`tb_excerpt`、`lesson_position`、`module_rows` 在各任务间名称一致。

**4. Review Focus** — 五项均已在对应任务的测试中钉住：
空状态（Task 5/7/8/10 的 `.tb-empty`）、长内容（Task 1 的 `nowrap`+`min-width`、Task 6）、
深色语义色（Task 1 的 token 覆盖测试、Task 6 的 `#111827` 移除）、
离线页（Task 11）、未知枚举（Task 2）。

**5. Proportion** — 计划约 600 行，覆盖 14 个模板 + 1 份 CSS + 3 个 Python 模块；未粘贴完整模板代码。