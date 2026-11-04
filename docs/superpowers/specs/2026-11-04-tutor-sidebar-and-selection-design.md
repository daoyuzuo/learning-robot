# 浮动追问栏与划词引用（Design）

- 状态：Approved（方向 B + 划词引用），2026-11-04
- 上游：对话中的三版实物稿 `ui-audit/mockups/tshot/{a,b,c}.png`，用户选择 **B**
- 目标：在课程页把追问从“页面最底部的一张卡”改为**右侧常驻栏**，并让提问
  自动带上用户选中的正文文字
- 范围：`web/templates/lesson.html`、`web/static/tb.css`、`web/static/tb-runtime.js`、
  `web/app.py`、`src/testbridge/tutor/{service,prompts,store,parse}.py`

---

## 1. 问题

现状：`lesson.html` 把 `section.tb-tutor` 放在正文、资源、上下课导航之后。
课程正文实测 2400px 以上，读到中段想问一句，必须滚到页尾；问完再想回到原处，
还得自己找回阅读位置。历史是页面内的一串平铺消息，与正文不同屏，无法边读边对照。

## 2. 目标 / 非目标

**目标**

1. 阅读时提问入口始终可见，不必滚到页尾。
2. 正文与追问历史可以同时看见（≥1280px）。
3. 选中正文任意一段，提问时自动作为 `<selection>` 送给模型，并在界面上回显。
4. 窄屏（<1280px）自动退化为右下角浮钮 + 抽屉，不破坏 320px 无横向滚动。
5. 全站 CSP 不变：不使用内联 `style`/`script`，交互全在 `tb-runtime.js`。

**非目标**

- 不做多会话管理（一个课程一份历史，与现状一致）。
- 不做划词后自动弹小按钮（选中即记录锚文本，由用户决定是否提问）。
- 不改掌握度、证据、判分语义；追问仍然不进证据。
- 不改 `tb/1` 内容契约。

## 3. 布局

### 3.1 ≥1280px：两栏

```
main.tb-main.tb-lesson-main        （max-width: 1180px）
└── div.tb-lesson-shell            （grid: minmax(0,1fr) 400px; gap 40px）
    ├── div.tb-lesson-column       （max-width: 46rem，正文 + 目标 + 资源 + pager）
    └── aside.tb-tutor.tb-card     （position: sticky; top: 82px; 高度 clamp）
        ├── header 追问 + 条数
        ├── div.tb-tutor-log       （overflow-y: auto）
        └── form.tb-tutor-form     （锚点 pill / 选中引用 / 输入 / 发送）
```

- `tb-main.tb-lesson-main` 的 `max-width` 从 46rem 提到 1180px；正文列继续
  `max-width: 46rem`，保持既有阅读尺度不变。
- 侧栏 `position: sticky; top: 82px; max-height: calc(100vh - 110px);`
  历史区独立滚动，输入框固定栏底。

### 3.2 <1280px：浮钮 + 抽屉

- `.tb-tutor` 改为 `position: fixed` 右侧抽屉（宽 400px，`transform: translateX(100%)`），
  由 `.tb-tutor-fab` 按钮切换 `[data-open="true"]`。
- `≤760px`：抽屉全宽。
- 浮钮固定在右下角，显示未读/记录数。

## 4. 划词引用

### 4.1 采集

`tb-runtime.js` 监听正文容器 `.tb-lesson` 上的 `mouseup` 与 `keyup`：

- 用 `window.getSelection()` 取选区；为空、或选区不在 `.tb-lesson` 内则忽略。
- 归一化空白，截断到 **400 字**（超出提示“已截取前 400 字”）。
- 存入 `data-selection`，在输入框上方渲染一行引用块：

```
┌ 引用正文 ─────────────────────────────┐
│ 策略决定资源投向，计划决定排期……      │  ×
└───────────────────────────────────────┘
```

- 点 × 清除；再次选中则替换。
- 悬停引用块高亮正文中对应文字不可靠（不做），仅回显文本。

### 4.2 锚点联动

选中文字所在的小节标题（向上最近的 `h2`）自动写入锚点下拉框；用户仍可改回“整节课”。

### 4.3 传输

`POST /api/tutor` 增加 `selection: str = ""` 字段。

后端 `TutorService.ask(..., selection="")`：

- `MAX_SELECTION_CHARS = 400`，超出截断，不做报错（划词长度不可控，拒绝太粗暴）。
- 空字符串视为无引用。
- 进入提示词：在 `<lesson>` 之后、`<history>` 之前插入

```
<selection>
用户选中的正文片段：
……
</selection>
```

`SYSTEM_PROMPT` 增加一条：

> 9. 有 `<selection>` 时，优先针对该片段回答；若问题与该片段无关，按问题回答并说明。

### 4.4 持久化

`tutor_message` 增加 `selection TEXT NOT NULL DEFAULT ''`。

- 采用幂等迁移：建表 SQL 保持不变，初始化时 `PRAGMA table_info` 检查列，
  缺失则 `ALTER TABLE ... ADD COLUMN`。已有库不清空、不重建。
- `TutorMessage` 增加 `selection: str = ""`；`history()` 读出；历史渲染显示引用块。

## 5. 接口

```python
TutorService.ask(lesson_id, anchor, question, *, use_web=True, selection="") -> TutorReply
render_user_prompt(context, anchor, question, history, *, web_hits=None, today=None, selection="")
TutorStore.append(..., selection="") -> TutorMessage
TutorStore.history(...) -> list[TutorMessage]   # 每条带 selection
```

`web/app.py::TutorRequest`：

```python
class TutorRequest(BaseModel):
    lesson_id: str
    anchor: str = ""
    question: str
    web: bool = True
    selection: str = ""
```

## 6. 测试

- `tests/test_tutor_selection.py`（新）：
  - 选中文字进入提示词 `<selection>` 块；
  - 超过 400 字被截断且不报错；
  - 空 selection 不产生 `<selection>` 块；
  - 落库后 `history()` 带回 selection；
  - 旧库（无 selection 列）初始化后自动补列且不丢数据。
- `tests/test_tutor_web.py` 扩充：`/api/tutor` 接受 `selection` 并原样进历史。
- `tests/test_web_ui.py`：保留 `class="tb-tutor tb-card"`（断言依赖）；
  新增课程页含 `tb-lesson-shell` 与 `tb-tutor-fab`。
- `tests/test_layout_guards.py`：1280px 以下的两栏折叠规则存在。
- 全量 `pytest` 不回归（基线 658）。

## 7. 验收

- 1440px：正文与追问同屏，历史可滚动，输入框常驻；滚动正文时侧栏不动。
- 320px：无横向滚动；抽屉可开合；浮钮可点。
- 选中正文一段 → 输入框上方出现引用块 → 发送 → 请求体含 `selection`，
  历史中该条显示引用。
- `pytest` 全绿；`tb build` 离线页不受影响（不引用 tb-runtime 的追问逻辑之外的部分）。

## 8. 留给实施者

- 抽屉动画时长与缓动（沿用 `prefers-reduced-motion` 兜底）。
- 引用块的截断提示文案。
- 浮钮是否显示未读数（本轮显示记录总数，不做未读概念）。