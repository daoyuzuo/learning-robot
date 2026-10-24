# AI 技术教学：开源项目与 Skill 调研

> 调研时间：2026-10-24。star 数来自 GitHub API，仅代表热度，不代表质量。
> 关注四条能力轴：**资源怎么找 → 课程怎么排 → 怎么引导 → 怎么媒体化**。
> 最后一节给出对本项目设计的启示。

---

## 0. 结论先行

**有，而且不少；但没有一个项目把四件事都做好。** 现成项目大致落在四层，最好拆开抄：

| 层 | 最强参考 | 一句话 |
|---|---|---|
| 教学工作流 / Skill | **mattpocock/skills 的 `teach`** | 把目录变成长期教学工作区：MISSION、RESOURCES、lessons、learning records |
| 课程生成 / 课堂体验 | **THU-MAIC/OpenMAIC** | 一句话/一份文档 → 大纲 → 多节课 → slides、quiz、交互仿真、PBL |
| 自适应排课引擎 | **ArnaudGuiovanna/tutor-mcp** | 技能图 + 先修关系 + BKT + FSRS，把"下一步学什么"做成确定性算法 |
| 知识库 / 长期学习 | **HKUDS/DeepTutor** | 多引擎 RAG + Mastery Path + 可视化 + Manim + 可审计记忆 |
| 教学法词典 | **GarethManning/education-agent-skills** | 165 个循证教学 skill，覆盖课程设计、提问、评估、学生引导 |
| 交互式白板 | **HugeCatLab/ChatTutor** | 教师 Agent 调用白板工具，实时画图、公式、思维导图 |

如果只看三个：**`teach`（工作流）+ OpenMAIC（生成与媒体）+ tutor-mcp（排课算法）**。

**核心判断：教学产品的护城河不在聊天框，而在领域知识图谱、资源可信度、评分 rubric 和反馈闭环。** 通用项目都能生成"看起来像课"的内容，但不能判断"对你的目标而言，下一步该学什么、学没学会"。

---

## 1. 生态全景

| 类别 | 项目 | 形态 | 许可 | 热度（约） | 最适合借鉴 |
|---|---|---|---|---|---|
| 教学 Skill | [mattpocock/skills · teach](https://github.com/mattpocock/skills) | Claude/Codex Skill | MIT | 302k | 长期教学工作区、资源策展、HTML lesson |
| 教学 Skill 库 | [GarethManning/education-agent-skills](https://github.com/GarethManning/education-agent-skills) | 165 个 Skill | CC BY-SA 4.0 | 900 | 课程设计、提问、评估、学生引导 |
| 中文教学 Skill | [chentao326/teacher-skill](https://github.com/chentao326/teacher-skill) | Claude Skill | MIT | 64 | 学情诊断、分级教学、名师风格模仿 |
| 中文教学 Skill | [flysheep-ai/education-skills](https://github.com/flysheep-ai/education-skills) | Claude Skill 集合 | MIT | 117 | 高考/学科辅导的提示词结构 |
| 提示词导师 | [JushBJJ/Mr.-Ranedeer-AI-Tutor](https://github.com/JushBJJ/Mr.-Ranedeer-AI-Tutor) | Prompt | 无 | 29.5k | 学习者画像、深度/风格/节奏可配置 |
| 课程生成 | [THU-MAIC/OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) | Next.js 平台 | MIT | 41k | 课程级规划、多智能体课堂、交互媒体 |
| 长期学习 | [HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor) | Python 平台 | Apache-2.0 | 42k | 多引擎 RAG、Mastery Path、Book、Manim |
| 自适应引擎 | [ArnaudGuiovanna/tutor-mcp](https://github.com/ArnaudGuiovanna/tutor-mcp) | MCP Server (Go) | MIT | 54 | 技能图、BKT、FSRS、掌握度门控 |
| 交互白板 | [HugeCatLab/ChatTutor](https://github.com/HugeCatLab/ChatTutor) | Web 应用 | AGPL-3.0 | 1.3k | DSL 白板、Geogebra、思维导图 |
| 教师备课 | [SirhanMacx/Claw-ED](https://github.com/SirhanMacx/Claw-ED) | Python 本地应用 | MIT | 63 | 教学风格画像、教案/学案/PPT 生成 |
| 文档转课程 | [StudentTraineeCenter/edu-agent](https://github.com/StudentTraineeCenter/edu-agent) | LangGraph + RAG | MIT | 23 | 学习计划、测验、闪卡、语义思维导图 |
| 本地教研助手 | RUCAI（Cambridge 论文） | Ollama + pgvector | MIT | 研究 | 来源可追溯、冻结语料的学生实例 |
| 溯源式学习 | [John-MiracleWorker/open-tutor](https://github.com/John-MiracleWorker/open-tutor) | 本地应用 | MIT | 0（alpha） | 生成与验证分离、确定性判定掌握度 |
| 资源索引 | [edtechdev/aied](https://github.com/edtechdev/aied) | 知识库 | MIT/CC0 | — | 持续更新的 AI 教育项目与论文索引 |

> 注意：`teach` 属于一个 30 万 star 的 Skill 合集，不是独立教学平台；Mr. Ranedeer 没有许可证，只能借鉴提示词结构，不要拷代码。

---

## 2. 资源怎么找（Resource Discovery）

### 2.1 三种范式

| 范式 | 做法 | 代表 | 优点 | 风险 |
|---|---|---|---|---|
| **策展式** | 先建 `RESOURCES.md`，人工/半自动筛选高信任来源，再基于资源备课 | `teach` | 质量高、可解释 | 覆盖慢，依赖人 |
| **检索式** | Agent 调 web search + fetch，边查边写，附引用 | OpenMAIC | 覆盖广、时效好 | 幻觉、来源质量参差 |
| **语料式** | 上传 PDF/教材/标准，切分索引，只在该语料内回答 | DeepTutor、RUCAI、Claw-ED | 可控、可溯源 | 受限于已有语料 |

**成熟产品通常三者组合**：策展定边界 → 检索补时效 → 语料保准确。

### 2.2 各项目的具体机制

**`teach`：把"找资源"当成教学的前置条件**

- 原话是 **"Never trust your parametric knowledge"**：在 `RESOURCES.md` 填好之前，重点不是讲课，而是找高质量资源。
- 学习被拆成三件事：**Knowledge**（来自高信任资源）、**Skills**（互动练习）、**Wisdom**（进入真实社区/从业者圈子）。
- 课程里要求"littered with citations"，每个论断尽量给外部链接。
- 资源不是一次性搜索结果，而是随课程演进的工作区文件，后续 lesson 复用。

**OpenMAIC：课程生成 + 联网研究**

- 课程构建 Agent 可以规划多节课、搜索已解析材料、抓取可信 URL、复用素材媒体。
- 支持可插拔的 web search / webFetch provider（版本演进中接过 Kimi、DeepSeek、Firecrawl，早期也有 SearXNG 等）；provider 凭据不下发到浏览器。
- v1.3.0-rc 引入**知识库**：上传材料按文件夹长期保存、只解析一次，课程对话可通过 `@` 引用。

**DeepTutor：多引擎 RAG，把"资源"做成可切换的后端**

- 支持 LlamaIndex、PageIndex、GraphRAG、LightRAG、FAISS、Obsidian vault、Kiwix ZIM 离线百科、WeKnora、腾讯 IMA、MarginNote 等。
- 有 source figures、paged Office preview、引用回链，强调"来源完整"。
- 适合"我有一堆标准/教材/论文，要在里面教"的场景。

**Claw-ED / RUCAI：先把老师的语料变成"教学资产"**

- Claw-ED：导入 PDF/DOCX/PPTX/TXT/Markdown → 抽取文本、建立检索索引、生成**教学风格画像**；生成时先检索自己的材料。
- RUCAI：检索范围限定在教师索引的语料内，强调**来源可追溯、不确定性标注、证据范围控制**；可发布"学生实例"，冻结语料 + prompt 快照。
- 这类设计对"技术标准/内部文档"教学特别合适：宁可答"资料里没有"，也不要编。

**open-tutor：生成与验证分离**

- 本地模型可以提出课程和草稿，但**不能认证事实、不能授予掌握度**；掌握度由确定性代码根据证据判定。
- 这是防"AI 自评自夸"的一个激进但值得借鉴的设计。

### 2.3 资源检索工具箱

| 类型 | 工具/来源 | 说明 |
|---|---|---|
| 元搜索 | **SearXNG** | 自建、无需 API key、可聚合多引擎；适合本地优先产品 |
| 网页抓取 | Firecrawl、Jina Reader、Playwright | 把网页转干净 Markdown；注意 robots/ToS |
| 学术 | arXiv API、OpenAlex、Semantic Scholar、PubMed | 论文元数据、引用关系、开放获取全文 |
| 教材/OER | OpenStax、LibreTexts、OER Commons、Wikibooks | 可引用的开放教材 |
| 离线百科 | Kiwix ZIM | 无网环境/低成本部署 |
| 视频 | YouTube Data API、Bilibili 搜索 | 课程字幕是很好的教学风格与知识来源；遵守平台条款 |
| 代码/文档 | GitHub API、官方 docs | 技术教学的第一优先级来源 |
| 社区 | Reddit、Discord、论坛、Stack Overflow | `teach` 所说的"Wisdom"层 |
| 项目索引 | edtechdev/aied、olud.ai | 继续挖项目的入口 |

### 2.4 建议的资源可信度分级

给每个资源打标签，而不是只存 URL：

| 级别 | 来源 | 使用方式 |
|---|---|---|
| A | 官方文档、标准原文、同行评审论文 | 可直接作为事实依据 |
| B | 高质量教材、大学课程、维护良好的开源项目 | 可作主要学习材料，关键结论回溯 A |
| C | 技术博客、会议演讲、视频教程 | 作补充/直觉建立，需交叉验证 |
| D | 论坛回答、AI 生成内容、未署名文章 | 只作线索，不直接进课程正文 |

每条资源至少记录：`url / 作者 / 日期 / 覆盖概念 / 可信度 / 是否核验 / 许可证 / 摘录`。

---

## 3. 课程怎么排（Sequencing）

### 3.1 五种排课逻辑

1. **目标倒推（Backwards Design）**：先定义"学完能做什么"（可观察的表现），再倒推评估方式，最后排内容。`education-agent-skills` 的课程设计域就是这套。
2. **前置依赖图（DAG）**：概念是节点，先修关系是边；没有掌握前置，不进入后继。`tutor-mcp` 的核心。
3. **掌握度驱动（BKT）**：用贝叶斯知识追踪估计"此刻学会的概率"，低于阈值就继续练/换讲法。`tutor-mcp`、`open-tutor` 都用。
4. **遗忘曲线驱动（FSRS）**：按记忆稳定性安排复习，而不是固定"第 1/3/7 天"。`tutor-mcp`、`cognits`，以及本项目规划的 `py-fsrs` 都属此类。
5. **最近发展区（ZPD）**：基于学习记录选"跳一跳够得着"的内容。`teach` 用 `learning-records/*.md` 计算 ZPD。

### 3.2 项目对照

| 项目 | 排课机制 | 值得抄的点 |
|---|---|---|
| `teach` | MISSION → learning records → ZPD → 下一课 | 每节课只教一个"紧密范围"的点，必须有一个可感知的小胜利 |
| `tutor-mcp` | 技能图 + 先修规则 + BKT + FSRS + 评估证据 | 掌握度不到阈值，**拒绝**进入迁移测试；推荐理由可审计 |
| OpenMAIC | 课程级规划（一本书拆成多节）→ 每节 scene | 大纲与单节分离；可中断、可 steer、可导出 |
| DeepTutor | Mastery Path（带来源）、Book 章节化 | 路径上的每一步都能回到来源 |
| `teacher-skill` | 诊断 → 分级 → 渐进路径 → 单元确认 | 中文教学语境、进度持久化、艾宾浩斯复习 |
| `education-agent-skills` | 逆向设计、学习进阶、差距分析、 rubric | 教学法层面的"为什么这样排" |
| `edu-agent` | 文档 → 学习计划 + 测验 + 闪卡 + 思维导图 | 从静态材料自动生成多形态练习 |

### 3.3 一个可落地的数据模型

```yaml
concept:
  id: ros2-topic-qos
  title: ROS2 Topic 与 QoS
  domain: ros2
  target_level: L3          # L1 知道 / L2 理解 / L3 应用 / L4 取舍
  prerequisites: [ros2-node, pub-sub]
  related: [ros2-executor, sensor-qos]
  evidence:                 # 怎样算学会
    - 能解释 reliability 与 durability 的区别
    - 能针对传感器/控制指令选择 QoS
    - 能在故障案例中定位 QoS 不匹配
  resources: [doc-ros2-qos, book-ros2-03]
  lesson: lessons/0012-ros2-qos.html
  mastery: 0.42             # BKT 估计
  last_review: 2026-10-20
  next_review: 2026-10-27   # FSRS 调度
```

**排课算法的最小版本**（不引入 BKT 也能跑）：

```
候选 = 所有未达标概念
过滤 = 前置全部达标 且 target_level 未达到
排序 = 目标相关度 × 0.4 + 先修紧密度 × 0.3 + 复习到期 × 0.2 + 未接触惩罚 × 0.1
输出 = 取前 N 个，其中最多 1 个是复习、最多 1 个是跨域关联
```

有了数据再上 BKT/FSRS；不要一开始就上算法，先把概念、先修、证据三件事定义清楚。

### 3.4 排课落地建议

- **概念规模**：先做 60–80 个节点，不要一上来铺 300 个。
- **分层建图**：基础概念 → 核心概念 → 领域概念 → 加分项；每层只保留真正影响目标的节点。
- **两种边**：先修边（硬约束）+ 关联边（同一能力在不同场景下的映射）。
- **学习单元**：15–25 分钟一个 lesson；每个 lesson 只服务一个概念或一对强关联概念。
- **节奏**：以周为单位，新学 + 到期复习 + 一次综合检验；检验结果回写证据。
- **评估挂到概念**：每个评分维度都应对应概念 ID，避免“分数很高但不知道会什么”。

---

## 4. 如何引导（Guidance）

### 4.1 教学循环

```
诊断起点 → 明确本次目标 → 小步讲解 → 检查理解 → 练习 → 即时反馈 → 记录 → 安排复习
```

`teacher-skill` 的中文流程几乎是这个模板：先问"你之前学过吗、了解多少"，再说明"学完你能做什么"，讲一个点就确认一次，然后继续。

### 4.2 引导技术清单

| 技术 | 做法 | 来源/参考 |
|---|---|---|
| **苏格拉底提问** | 不直接给结论，用问题暴露假设和矛盾 | education-agent-skills 的 questioning-discussion 域 |
| **渐进提示阶梯** | 澄清 → 方向 → 局部步骤 → 具体例子 → 完整答案；每次只升一级 | Domain 20 的 progressive hint ladder |
| **先解释再追问** | 让学生先复述/解释，再针对漏洞提问 | explain-first interrogator |
| **误解检测** | 识别典型错误模式，而不是只判对错 | misconception detector 类 skill |
| **掌握度门控** | 未达阈值不进入下一层/迁移题 | tutor-mcp：0.33 < 0.85 时拒绝迁移 probe |
| **等长选项** | 选择题每个选项字数接近，正确项位置随机 | `teach` 的明确规则，减少格式线索 |
| **即时反馈** | 练习后立刻给对错与原因，延迟反馈只用于复习 | `teach` 的 feedback loop |
| **学习记录** | 记录"非显而易见的洞察"，驱动下一次 ZPD | `teach` 的 learning-records |
| **风格适配** | 模仿某位老师的句式、节奏、类比 | `teacher-skill` 可从 SRT/VTT 字幕提取风格 |

### 4.3 关键设计：流畅度错觉

`teach` 区分两种强度：

- **Fluency strength**：当下能想起来 → 容易产生"我学会了"的错觉。
- **Storage strength**：长期留存 → 才是目标。

对应的三条手段：**检索练习**（合上书回忆）、**间隔**（分散到多天）、**交错**（相关技能混练，仅用于技能）。这比"讲得更清楚"更能决定长期效果。

### 4.4 引导的反模式

- 一上来直接给答案/完整代码 → 学生看懂了，但没学会。
- 一次讲太多 → 工作记忆溢出；`teach` 明确要求 lesson 短。
- 只问"懂了吗" → 得到的是礼貌性点头；要问"你能用自己的话解释吗/预测下一步吗"。
- 无学习记录 → 每次从零开始，无法算 ZPD。
- 只追求流畅度 → 当天测试很好，一周后归零。
- AI 自评掌握度 → 生成与评估必须是两个角色/两套证据。

---

## 5. 怎么媒体化（Media）

### 5.1 五种形态与适用场景

| 形态 | 成本 | 适用 | 代表 |
|---|---|---|---|
| **自包含 HTML lesson** | 低 | 90% 的知识讲解 + 小测验 + 图示 | `teach` |
| **交互式 widget / 仿真** | 中 | 参数可调、观察因果（QoS、调度、滤波、PID） | OpenMAIC Deep Interactive |
| **白板/DSL 动画** | 中 | 推导过程、时序、状态变化 | ChatTutor |
| **Manim 动画** | 高（需渲染） | 数学、算法、几何 | DeepTutor、VidyaBot、Mimir |
| **多智能体课堂** | 高 | 沉浸式、AI 同学提问/辩论 | OpenMAIC |

### 5.2 各项目做法

**`teach`：HTML + 可复用 assets**

- 每节课一个自包含 HTML，编号 `0001-<name>.html`，Tufte 风格，可打印。
- `./assets/` 放共享样式、quiz 组件、模拟器、图表 helper；**复用是默认，不是例外**。
- 课程之间用 HTML 锚点互链；`./reference/*.html` 放速查表/术语表。
- 这是性价比最高的方案：不需要前端框架，也不需要渲染服务。

**ChatTutor：教师 Agent + 白板工具**

- 教师 LLM 调工具，交给"Painter" LLM 输出自定义 DSL，客户端渲染成多页白板。
- 支持 mermaid 思维导图、公式、代码、可交互数学图形（如滑块绑定 `theta`，单位圆上的点实时移动）。
- 集成 Geogebra；一切在浏览器端响应式渲染，不需要先编译视频。
- 适合"讲推导/讲几何直觉"，不适合大规模课程生产。

**OpenMAIC：场景化课堂**

- 标准模式：slides、quiz、交互式 HTML 仿真、PBL。
- Deep Interactive Mode：3D、仿真实验、小游戏、思维导图、在线编程五类交互 UI；AI 教师可操作 UI 并高亮讲解。
- 白板 + TTS + AI 同学提问/辩论 + 实时批改。
- 导出：保留所有 scene 的 `.pptx`、可离线播放的单个 `.html`、或课堂 ZIP。
- 这是目前"课程级媒体化"最完整的开源实现。

**DeepTutor：Book + Visualize**

- Book 每章编译成可编辑的 typed blocks：文本、callout、quiz、Manim 动画、交互 widget。
- Visualize 模式有插件化目录；支持把来源图片送入视觉模型。
- Manim 是可选依赖（需要 LaTeX/ffmpeg），适合数学/算法，不适合每节课都用。

**小工具**

- `agent-whiteboard`（npm）：给 Agent 的 step-frames 渲染协议，支持 mermaid、KaTeX、Vega-Lite、SVG、HTML，可分步播放并导出单文件 HTML。
- Mimir：Excalidraw 画布 + 手绘标注转 base64 给 Claude 视觉 + Manim 生成 + 对话分支树；hackathon 项目，设计参考价值大于代码。
- VidyaBot：文本 + Chart.js + HTML5 canvas 白板动画 + HeyGen 数字人，三条流水线并行。
- penmentor：读取手写数学作业，在屏幕上标注提示而不是给答案，可框选生成 Manim 动画；跑在 Claude Code/Codex CLI 上。

### 5.3 技术选型建议

| 需求 | 建议 |
|---|---|
| 普通知识讲解 | 自包含 HTML + 共享 CSS + 少量 JS |
| 公式 | KaTeX（比 MathJax 轻） |
| 流程图/状态机/时序 | Mermaid |
| 可调参数的图 | 原生 SVG/Canvas 或 JSXGraph；数学几何用 Geogebra |
| 3D/机器人场景 | Three.js / Babylon.js |
| 算法动画 | Manim（异步队列，别阻塞主流程） |
| 可运行代码 | Pyodide（Python）/ Sandpack（JS） |
| 导出 | 优先单文件 HTML；教学交付再加 PPTX/PDF |

**原则：能用 HTML/CSS/SVG 解决的，不要上视频。** 视频难改、难检索、难复用；交互图可以改一个参数就复用一学期。

### 5.4 技术教学的媒体清单

- **协议/帧结构**：可点击的字段图，悬停解释每个字段，切换模式看差异。
- **系统时序**：可播放的时序图，可调参数观察延迟、丢包、抖动。
- **状态机**：Mermaid 状态图 + 点击某条边看对应用例。
- **故障树**：交互式分支图，选现象 → 缩小根因范围。
- **指标仪表盘**：小型 SVG 仪表，配“这个数说明什么”的解释。
- **评分雷达图**：按 rubric 维度展示，和概念 mastery 联动。
- **概念地图**：全局 DAG + 当前 ZPD 高亮，作为学习首页。

---

## 6. 项目卡片（按可用性排序）

### 6.1 可以直接用的

**mattpocock/skills · `teach`**（MIT，302k）
长期教学工作区范式。产物是 `MISSION.md`、`RESOURCES.md`、`lessons/*.html`、`reference/*.html`、`learning-records/*.md`、`assets/*`。适合"我要认真学一个主题，持续数周"。
注意：它是 Skill，不是应用；需要 Claude Code/Codex 等宿主。

**THU-MAIC/OpenMAIC**（MIT，41k，v1.3.0-rc）
一句话/文档 → 完整互动课堂。课程级规划、24 个内置 skill、多智能体、白板/TTS、五类交互 UI、PPTX/HTML/ZIP 导出。适合快速生成课程与演示。
注意：部署较重（Next.js + PostgreSQL），功能多，定制要读源码。

**HKUDS/DeepTutor**（Apache-2.0，42k，v1.6.x）
长期个性化学习工作台。多引擎 RAG、Mastery Path、Book、Visualize、Manim、三层可审计记忆、MCP/CLI、IM 渠道。适合"以知识库为中心"的学习系统。
注意：功能面很宽，学习和运维成本高；先只用 RAG + 课程模式。

**GarethManning/education-agent-skills**（CC BY-SA 4.0，900，165 skills）
教学法词典。20 个域，覆盖课程对齐、课程评估、显性教学、提问讨论、记忆与学习科学、自我调节学习、学生端引导等。适合在写自己的教学 prompt 时查"这一步的教育学依据"。
注意：作者明确说未经实证验证为 AI 干预；CC BY-SA 有传染性，商用/闭源要评估。

**chentao326/teacher-skill**（MIT，64，v2.7.0）
中文 AI 老师。学情诊断、分级教学、10 个学科策略、名师风格模仿（字幕/视频）、进度持久化、刻意练习、艾宾浩斯复习、渐进路径。
注意：个人项目，更新到 2026-06；适合借鉴中文话术和流程。

**HugeCatLab/ChatTutor**（AGPL-3.0，1.3k）
可视化交互 AI 教师。白板 DSL、Geogebra、mermaid 思维导图、客户端响应式。
注意：AGPL，闭源商用需谨慎；原 `sheepbox8646/ChatTutor` 已迁移到此仓库。

### 6.2 适合借鉴设计的

**ArnaudGuiovanna/tutor-mcp**（MIT，54，alpha）
"生成式教学 + 确定性教学法"：LLM 负责创造和解释，BKT/FSRS/先修规则/评估证据负责推进。技能图可版本化，推荐理由可审计，掌握度不到阈值会拒绝迁移测试。支持本地/自建/机构三种部署。
注意：alpha，Go 二进制，生态小；抄模型和规则，不要指望开箱即用。

**SirhanMacx/Claw-ED**（MIT，63，beta）
本地优先教师助手。导入既有教案/课件 → 教学风格画像 → 生成教师版 DOCX、学生版 DOCX、PPTX；有来源清单、质量检查、差异化材料。单教师实例，不是多租户平台。
注意：偏 K12 教师备课，但"风格画像 + 来源清单 + 质量检查"很值得抄。

**StudentTraineeCenter/edu-agent**（MIT，23）
LangGraph + RAG，把静态文档转成学习计划、测验、闪卡、语义思维导图。适合看"一份文档如何拆成多种练习形态"。
注意：2025-12 后更新少。

**RUCAI**（MIT，研究论文）
本地优先教研助手，Ollama + PostgreSQL + pgvector；来源可追溯、不确定性标注、检索范围限定；可发布冻结语料的学生实例。
注意：偏研究原型，工程成熟度未知；设计原则很值得抄。

**John-MiracleWorker/open-tutor**（MIT，0，alpha）
生成与验证分离：本地模型提课程，确定性代码判掌握度。BKT + FSRS。
注意：0 star、alpha，只看设计。

**JushBJJ/Mr.-Ranedeer-AI-Tutor**（无许可证，29.5k）
经典提示词导师：学习者画像（深度、学习风格、沟通风格、语气、推理框架）可配置。
注意：无许可证，不能直接复用代码/提示词到商业产品；且 2025-09 后未更新。

**flysheep-ai/education-skills**（MIT，117）
中文高考导向的教学 skill 集合，分学科、渐进/启发式教学。适合看中文 K12 的提示词组织。

**edtechdev/aied**（MIT/CC0）
AI 教育知识库，自动扫描 arXiv/期刊，持续更新项目、论文、工具。用来继续挖项目。

### 6.3 不建议直接用的

- 0 star / alpha / 无许可证的项目：只做设计参考。
- 纯 prompt 项目：容易受模型版本影响，且难评估。
- 重前端、重多智能体的项目：如果目标是 10–15h/周做出可用产品，维护成本过高。
- AGPL/CC BY-SA 项目：先确认分发方式，再决定是否引用代码/文本。

---

## 7. 按目标选型

| 你的目标 | 首选 | 怎么用 |
|---|---|---|
| 快速生成一门课并演示 | OpenMAIC | Docker 起服务，先用标准模式，再试 Deep Interactive |
| 长期认真学一个主题 | `teach` | 建工作区，先写 MISSION，再让 Agent 找资源、做 lesson |
| 做自适应排课 | tutor-mcp | 抄技能图 + BKT + FSRS + 门控；不要抄 Go 实现 |
| 做知识库问答 | DeepTutor / RUCAI | 先用 RAG + 引用，别急着上多智能体 |
| 做交互式讲解 | ChatTutor / `teach` assets | 简单图用 HTML/SVG；推导用白板 DSL |
| 做教师备课工具 | Claw-ED + education-agent-skills | 风格画像 + 教案模板 + 教学法 skill |
| 做中文教学产品 | `teacher-skill` + flysheep | 借鉴诊断话术、分级策略、学科结构 |
| 继续找项目 | edtechdev/aied | 按主题检索，别只看 star |

---

## 8. 对本项目设计的启示

调研里的项目各有取舍，归纳成六条可直接落到设计里的原则。

### 8.1 内容契约

- 课程统一为 HTML 片段 + 机器可读 manifest；正文负责呈现，manifest 负责概念、练习、资源、证据。
- 共享 assets 与组件，避免每节课重复造样式和交互。
- 内容包可整包替换；引擎只认 schema，不认学科。

### 8.2 资源

- 资源不是链接列表，而是带可信度、覆盖概念、核验日期、许可证的记录。
- 策展、检索、语料三种方式组合：策展定边界，检索补时效，语料保准确。
- 生成内容必须附引用；关键结论回溯到一手资料。

### 8.3 排课

- 概念图 + 先修边是骨架；掌握度和复习是调度器。
- LLM 负责生成和解释，确定性算法负责“下一步学什么”。
- 先规则后 BKT；先 FSRS 后个性化策略。

### 8.4 引导

- 五级提示阶梯：澄清 → 方向 → 局部 → 具体 → 答案。
- 先解释再追问；记录误解，而不只记对错。
- 检索练习、间隔、交错，优先于“讲得更清楚”。

### 8.5 媒体

- 默认 HTML/CSS/SVG；只有必须观察动态时才上仿真或动画。
- 交互组件用引擎注册的渲染器，内容只提供 JSON 规格。
- 导出优先单文件 HTML；需要交付时再生成 PPTX/PDF。

### 8.6 证据

- 生成与验证分离：内容可以生成，掌握度必须由证据判定。
- 证据追加式存储；掌握度是派生值，可重建。
- 每个“学会了”的结论都能下钻到具体作答、实验或评分。

---

## 9. 风险与注意事项

| 风险 | 说明 | 应对 |
|---|---|---|
| 许可证 | ChatTutor 是 AGPL；education-agent-skills 是 CC BY-SA；Mr. Ranedeer 无许可证 | 商用/闭源前逐个确认；优先 MIT/Apache-2.0 |
| 幻觉 | 生成式课程容易编事实、编引用 | 强制引用；A 级来源回溯；生成与验证分离 |
| 自评偏差 | LLM 给自己出的题打分偏高 | 评分用独立 rubric/独立角色；关键结论用确定性检查 |
| 资源版权 | 抓取网页、视频字幕、教材 | 遵守 ToS/robots；优先开放许可资源；只存摘录与链接 |
| 维护成本 | OpenMAIC/DeepTutor 功能面大 | 只取需要的模块；先跑通最小闭环 |
| 本地模型质量 | 小模型教学效果不稳定 | 教学/评分用强模型；本地模型只做检索/格式化 |
| 过度媒体化 | 视频/3D 成本高、难改 | 默认 HTML；只有"必须观察动态"时才上仿真/动画 |
| 数据隐私 | 面试录音、简历、公司情报 | 本地优先；明确存储与删除策略 |

---

## 10. 参考链接

**项目与 Skill**

- [mattpocock/skills · teach](https://github.com/mattpocock/skills)
- [THU-MAIC/OpenMAIC](https://github.com/THU-MAIC/OpenMAIC)
- [HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor)
- [ArnaudGuiovanna/tutor-mcp](https://github.com/ArnaudGuiovanna/tutor-mcp)
- [GarethManning/education-agent-skills](https://github.com/GarethManning/education-agent-skills)
- [chentao326/teacher-skill](https://github.com/chentao326/teacher-skill)
- [flysheep-ai/education-skills](https://github.com/flysheep-ai/education-skills)
- [HugeCatLab/ChatTutor](https://github.com/HugeCatLab/ChatTutor)
- [SirhanMacx/Claw-ED](https://github.com/SirhanMacx/Claw-ED)
- [StudentTraineeCenter/edu-agent](https://github.com/StudentTraineeCenter/edu-agent)
- [John-MiracleWorker/open-tutor](https://github.com/John-MiracleWorker/open-tutor)
- [JushBJJ/Mr.-Ranedeer-AI-Tutor](https://github.com/JushBJJ/Mr.-Ranedeer-AI-Tutor)
- [edtechdev/aied](https://github.com/edtechdev/aied)

**论文/文档**

- DeepTutor: Towards Agentic Personalized Tutoring — arXiv:2604.26962
- OpenMAIC — JCST'26, DOI 10.1007/s11390-025-6000-0
- RUCAI: An Open-Source, Local-First AI Teaching Assistant — Cambridge University Press
- Agent Skills 标准 — https://agentskills.io

**资源检索**

- SearXNG — https://github.com/searxng/searxng
- Firecrawl — https://github.com/mendableai/firecrawl
- OpenAlex — https://openalex.org
- arXiv API — https://info.arxiv.org/help/api/
- OpenStax — https://openstax.org
- LibreTexts — https://libretexts.org
- Kiwix — https://www.kiwix.org
