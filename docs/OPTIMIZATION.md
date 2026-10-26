# TestBridge 优化清单（体验债）

- 状态：Spec 已写，待评审；O1 / O2 / O3 的方向已于 2026-10-26 确认（见 §0.1）
- 来源：P4.3 完成后的真实使用反馈
- 定位：跨期体验债，不是新一期设计。每项落地前按 `CLAUDE.md` 的流程补
  spec / 实施计划；涉及质量门禁或内容契约的先更新 spec 与 `ROADMAP.md`。
- 权威文件仍是 `ROADMAP.md` 与 P1/P2 总设计；本文只记录问题、根因、候选方案、
  验收标准与待确认项。

### 0.1 已确认决策（2026-10-26）

| 编号 | 决策 |
|---|---|
| O1 | 采用方案 A：一次性写入 Windows 用户环境变量，配 `tb doctor` 自检；不在仓库或项目目录落 `.env`，不改“密钥不落盘”边界。 |
| O3 | 允许 C 级工程博客/社区帖作为“补充阅读”，每课可有多条；`required` 资源仍只允许 A/B，C 级不计入 A/B 分子。 |
| O2 | 先只做第 1 层：结构化图形 → 服务端渲染 SVG；外部图片与 AI 生图暂缓。 |

### 0.2 Specs

| 编号 | Spec |
|---|---|
| O1 | [2026-10-26-o1-llm-config-persistence-design.md](superpowers/specs/2026-10-26-o1-llm-config-persistence-design.md) |
| O2 | [2026-10-26-o2-lesson-figures-design.md](superpowers/specs/2026-10-26-o2-lesson-figures-design.md) |
| O3 | [2026-10-26-o3-resource-quality-design.md](superpowers/specs/2026-10-26-o3-resource-quality-design.md) |
| O4 | [2026-10-26-o4-course-planning-dialogue-design.md](superpowers/specs/2026-10-26-o4-course-planning-dialogue-design.md) |
| O5 | [2026-10-26-o5-web-ui-polish-design.md](superpowers/specs/2026-10-26-o5-web-ui-polish-design.md) |

**进度：** O1 已实现（2026-10-26，分支 `p5-optimization`）。默认
`pytest` 756 passed、3 deselected；新增 14 个 CLI/环境测试。O3 待开始。

---

## 0. 总览

| 编号 | 主题 | 建议优先级 | 规模 | 是否触碰硬边界 | 建议顺序 |
|---|---|---|---|---|---|
| O1 | 模型配置一次生效 | P0 | S（0.5–1 天） | 否：只写 Windows 用户环境变量，不落仓库 | 1 |
| O3 | 参考资料工程化与可达性 | P1 | M（2–4 天） | 是：质量门禁的 trust / 来源语义 | 2 |
| O2 | 课程图文并茂 | P1 | M（2–3 天） | 否：本轮只做内联 SVG，不动契约 | 3 |
| O4 | 自动规划课时 + 对话修正 | P2 | M–L（3–5 天 + spec） | 否：只动 `studio/` 与草稿 | 4 |
| O5 | 页面排版与样式 | P3 | S–M（2–3 天，可增量） | 否：只动 `web/` | 5 |

建议顺序的理由：O1 每天都会挡路，先去掉摩擦；O3 直接决定学到的内容是否可信、
可读，是学习质量的最大变量；O2 在 O3 之后做，因为图需要引用和授权信息；
O4 是新能力，需要先想清楚交互与边界；O5 按你的意见放最后，可以随其它改动增量做。

---

## 1. O1：模型配置一次生效

### 1.1 现象

- 每开一个新终端、每次重启服务，都要重新 `export TESTBRIDGE_LLM_*`。
- `TESTBRIDGE_LLM_TIMEOUT` 默认 30 秒，生成整节课经常不够；临时调高只对当前
  终端有效，重启后回到默认值。
- 跑 `pytest`、开 Web、跑 `tb` 命令各自需要一套环境，容易漏。

### 1.2 现状

- 必需变量为 `TESTBRIDGE_LLM_BASE_URL` / `TESTBRIDGE_LLM_API_KEY` /
  `TESTBRIDGE_LLM_MODEL`，可选 `TESTBRIDGE_LLM_TIMEOUT`
  （[tutor/config.py:9-15](../src/testbridge/tutor/config.py#L9-L15)）。
- Web 启动时只读取一次配置
  （[web/app.py:129](../web/app.py#L129)），之后改环境变量必须重启服务。
- README 目前要求每个终端手动 `export`
  （[README.md:20-33](../README.md#L20-L33)）。
- 生成可靠性 spec 已经记录了“手工调高 timeout 只对当前终端有效”
  （[studio-generation-resilience-design.md:2.4](superpowers/specs/2026-10-26-studio-generation-resilience-design.md)）。

### 1.3 根因

配置只存在于“当前进程的环境变量”里，项目没有一次性写入用户级环境的手段，
也没有一个命令告诉用户“现在到底读到了什么”。

### 1.4 方案（2026-10-26 已确认采用 A）

**方案 A（采用）：写入 Windows 用户环境变量 + `tb doctor`。**

1. 新增 `tb env init`（或文档中的一次性脚本）：
   - 交互式询问 base URL / model / timeout，密钥用 `getpass` 输入；
   - 在 Windows 上写入用户级环境变量（`setx` 或 `winreg` + 广播变更），
     不写仓库文件；
   - 打印“请重开终端 / 重启服务”。
2. 新增 `tb doctor`（离线）：
   - 列出每个变量：`set` / `missing`，base URL 只显示 host，模型名原样显示，
     timeout 显示生效值；
   - **不打印密钥**，最多显示“已配置（长度 N）”；
   - 可选 `--probe` 才发一次最小请求，默认不联网，不影响默认 `pytest`。
3. README 增加 Windows 一次性配置段，并明确“改完要重启服务”。

优点：密钥仍然只在环境变量里，不落仓库、不进日志、不回显，符合现有硬规则。
缺点：仍然是“用户级持久化”，不是项目级；换机器要重做一次。

**方案 B（不采用）：用户级 `.env` 文件（需要改硬规则）。**

把配置放在仓库外的 `%APPDATA%\TestBridge\env`（或用户主目录），启动时读取。
需要明确修改 `CLAUDE.md` 的“密钥不落盘”边界为“不写入仓库、日志、URL，
文件权限受限”。还要新增解析代码或依赖 `python-dotenv`。
除非你明确要求，否则不推荐：它把“密钥是否安全”从环境变量转移到了文件权限上。

**方案 C（不采用）：Windows 凭据管理器 / keyring。** 安全性最好，但跨平台与
依赖成本高，当前单人本地使用不值得，暂不做。

### 1.5 验收

- 新开终端、不执行任何 `export`，`tb doctor` 显示配置齐全；启动 Web 后
  Studio 能调用模型。
- 密钥不出现在页面、日志、异常信息、`tb doctor` 输出中。
- 默认 `pytest` 不依赖真实环境变量（测试继续用 monkeypatch / 假客户端）。
- 文档写清：修改配置后需要重启 Web 服务；`TESTBRIDGE_LIVE=1` 只控制测试是否联网。

### 1.6 已确认 / 剩余待确认

- 已确认：写入 Windows 用户环境变量，作为一次配置的手段。
- 已确认：不引入仓库内 `.env`，保持“密钥不落盘”。
- 剩余小项：`tb doctor --probe` 默认关闭（离线）；是否要这个可选联网自检，
  实现时按“默认不做、加开关”处理即可。

---

## 2. O2：课程图文并茂

### 2.1 现象

课程基本是“文字 + 练习”，缺少示意图、框图、流程图、时序图、对比图；
希望至少能用网上找的图、AI 生成的图或自动生成的思路图。

### 2.2 现状

- 内容契约和净化器**已经允许** `img` / `svg` / `figure`
  （[sanitize.py:10-17](../src/testbridge/contract/sanitize.py#L10-L17)、
  [sanitize.py:27](../src/testbridge/contract/sanitize.py#L27)），样例课也用了本地
  `<img>`（[L-SYNC-001.html:22-23](../content-packs/sample-sensors/modules/M01/lessons/L-SYNC-001.html#L22-L23)）。
- 但写课提示词的“允许标签”清单里**没有 `img` / `svg`**
  （[prompts.py:30-31](../src/testbridge/studio/prompts.py#L30-L31)），模型因此不会
  主动产图；这是“没有图”的直接原因。
- Web 的 CSP 是 `img-src 'self' data:`
  （[web/app.py:118-120](../web/app.py#L118-L120)），外链图片会被浏览器拦截，
  所以“从网上找图”必须下载到本地。
- `tb build` 会复制 `assets/`（[build.py:255-257](../src/testbridge/build.py#L255-L257)）；
  含位图的构建产物是“目录 + 资源”，不是严格单文件。
- 没有图片规划、生成、授权、署名、校验流程；`Resource.url` 必须是 `http(s)`
  （[models.py:190-195](../src/testbridge/contract/models.py#L190-L195)），
  本地图片不能直接登记为 Resource。

### 2.3 方案（2026-10-26 确认：先只做第 1 层）

**第 1 层（采用，本轮范围）：结构化图形 → 服务端渲染 SVG。**

- 模型不直接画“任意 SVG”，而是输出受限的图形规格，例如：
  - `timeline`（时间线）、`flow`（流程/框图）、`block`（架构块图）、
    `compare`（左右对比）、`sequence`（时序）。
- 服务端用确定性渲染器把规格变成内联 SVG，再走 `sanitize_fragment` 落盘。
- 写课提示词增加：每课 1–2 张图，必须有 `figcaption` 和 `alt`；文字用中文；
  颜色使用 `currentColor` 以兼容深色模式。
- 好处：离线、确定性、文字清晰、无版权问题、无需图片模型；正好覆盖你说的
  “思路图 / 框图”。
- 风险：复杂拓扑图会显得刻板；先支持 4–5 种图形，不追求自由绘图。

**第 2 层（暂缓）：精选外部图片（可选，后做）。**

- 只接受明确许可的图：CC0 / Public Domain / CC-BY / CC-BY-SA；拒绝来源不明、
  付费墙内的图。
- 下载到 `assets/figures/`，记录来源 URL、作者、许可证、获取日期；页面展示署名。
- 需要决定署名信息的存放位置：
  - 侧车文件 `assets/figures/attribution.yaml`（不改 `tb/1`），或
  - 给课程 manifest 增加可选 `figures` 字段（需要 spec，按“只加可选字段”处理）。
  不要静默扩展 `tb/1`。
- 不允许热链，避免 CSP 失败、图片失效和版权问题。

**第 3 层（暂缓）：AI 生图（可选，默认关闭）。**

- 你愿意配置生图模型再上；新增 `TESTBRIDGE_IMAGE_*` 可选变量，未配置时完全
  不影响生成流程。
- 只用于“概念氛围图 / 场景插图”，不用于精确架构图（模型画不准文字和连线）。
- 生成文件存 `assets/figures/`，记录 prompt、模型、生成时间；页面明示“AI 生成”。
- 默认 `pytest` 不联网，测试用假客户端；不能成为核心链路的必需依赖。

### 2.4 质量与校验

- 本轮（第 1 层）新增确定性规则（warning/error 分级）：
  - 每课至少 1 张图（可配置，先 warning）；
  - `alt` 非空、`figcaption` 非空；
  - 本地 `src` 必须存在于 `assets/`；禁止外部 `img src`；
  - 图形规格渲染失败时回退为文字说明，不阻断整课。
- 外部来源授权与署名规则随第 2 层暂缓，不在本轮实现。
- `tb quality` 增加“图示覆盖”指标；不改变现有分数基线时以 warning 起步。

### 2.5 验收

- 新建 2 模块 × 2 课，写课后每课至少 1 张图；`tb validate` 0/0；
  `tb quality` 不因新规则产生硬错误。
- 在 Web 与 `tb build` 产物中图都能显示；离线打开无外链请求。
- 默认 `pytest` 全绿且不联网；图片渲染器有单元测试。

### 2.6 已确认 / 暂缓

- 已确认：本轮只做第 1 层（确定性 SVG），不接外部图片、不接 AI 生图。
- 暂缓：第 2 层的授权署名存储位置（侧车文件 vs manifest 可选字段）留到真正
  做外部图片时再定；届时优先侧车文件，避免动 `tb/1`。
- 暂缓：`TESTBRIDGE_IMAGE_*` 与生图客户端，等第 1 层用下来再评估。

---

## 3. O3：参考资料工程化与可达性

### 3.1 现象

- 资源偏学术论文，工程文档、厂商文档、工程博客、教程很少。
- 部分链接能访问但内容 404，或跳转到付费/登录页，实际读不到。

### 3.2 根因（按代码事实）

1. **自动路由几乎总走学术源。**
   `ACADEMIC_KEYWORDS` 包含“具身智能 / 机器人学习 / 强化学习 / 大模型”等，
   `ACADEMIC_DOMAINS` 包含 `embodied-ai`
   （[search_router.py:9-20](../src/testbridge/studio/search_router.py#L9-L20)）。
   你的主题正好命中，`auto` 会选 OpenAlex 为主、DeepSeek 只在无命中/失败时兜底
   （[search_router.py:102-126](../src/testbridge/studio/search_router.py#L102-L126)）。
   而且路由是**每课一次**，整课所有查询都走同一个后端
   （[web/studio.py:235-244](../web/studio.py#L235-L244)），不是按查询分流。
2. **写课只允许 A/B 级来源。**
   提示词要求“只引用 authority>=2 的条目”，trust 只能是 A/B
   （[prompts.py:43-46](../src/testbridge/studio/prompts.py#L43-L46)）；
   解析时非 A/B 直接报错
   （[lessons.py:24](../src/testbridge/studio/lessons.py#L24)、
   [lessons.py:87-88](../src/testbridge/studio/lessons.py#L87-L88)）；
   质量门禁对非 A/B 记硬错误
   （[provenance.py:117-129](../src/testbridge/quality/provenance.py#L117-L129)）。
   工程博客通常被上游标成 C，于是被**结构性排除**，不是“少”，是“进不来”。
3. **OpenAlex 链接优先给 DOI。**
   URL 选择顺序是 DOI → landing page → OA URL
   （[search_openalex.py:44-56](../src/testbridge/studio/search_openalex.py#L44-L56)）。
   DOI 往往落到出版社付费页，违反“可访问”的目标。
4. **可达性只在定稿时检查 HTTP 状态。**
   `verify_resources` 只 `GET` 一次、跟随跳转、看是否 `>=400`
   （[gates.py:61-78](../src/testbridge/studio/gates.py#L61-L78)）。
   软 404、登录页、付费墙页、空内容都可能返回 200，检查不出来；
   而且错误直到定稿才出现，反馈太晚。
5. **`last_verified` 是假日期。**
   写课时如果没有该字段，直接填当天
   （[lessons.py:99-100](../src/testbridge/studio/lessons.py#L99-L100)），
   并没有真的访问过；这会让“已验证”失去意义。
6. **没有来源类型多样性规则。**
   `Resource.type` 是自由字符串（[models.py:183](../src/testbridge/contract/models.py#L183)），
   质量门禁只看 trust 和元数据，不看“是否只有论文”“是否有工程来源”
   （[provenance.py:111-140](../src/testbridge/quality/provenance.py#L111-L140)）。

### 3.3 推荐方案

**A. 把“来源类型”变成一等公民。**

- 在调研与质量层定义来源类别（不急着改 `tb/1` 的 `type` 自由字符串）：
  `official_docs` / `standard` / `engineering_blog` / `tutorial` /
  `repository` / `paper` / `book` / `video`。
- 每模块的目标配比（建议值，可调）：
  - 至少 1 条官方文档 / 标准 / 仓库；
  - 至少 1 条工程博客 / 教程（有则必需，无则 warning）；
  - 论文可选，不再默认占满。
- 写课提示词：优先官方文档和工程实践；同一概念不要只给论文；每条资源写清
  `why`（“工程上什么时候用”）。

**B. 调研按查询分流，而不是整课一个后端。**

- 大纲阶段给每条 `research_query` 打标签：`academic` / `engineering` / `official`。
- `auto` 模式下逐查询路由：学术查询走 OpenAlex，工程查询走 DeepSeek Search；
  两者结果合并进同一份档案；手动选择仍保持“不静默回退”的现有契约。
- 补充工程向查询模板：`site:docs.ros.org`、`site:github.com`、厂商文档、
  `tutorial`、`best practices` 等；避免所有查询都以“论文/综述”开头。
- 保留 A/B 溯源规则：资源 URL 必须出现在档案里，不能让模型自由编 URL。

**C. 重新定义“B 级”的边界。**

- 把可确认的工程权威来源纳入 B：官方产品文档、标准组织公开页、主流开源项目
  文档、维护者工程博客、厂商技术博客。
- 已确认：C 级来源（普通博客、社区帖）允许作为“补充阅读”，每课可以有**多条**：
  - 新增 `role: required | supplementary`（`tb/1` 可选字段，需 spec）；
  - `required` 仍只允许 A/B，且每课至少 1 条；
  - `supplementary` 允许 C，每课可多条；建议软上限 3 条，超过只给 warning，
    不阻断（软上限做成可配置，不写死）；
  - C 级不计入“资源可信”分子，也不计入 A/B 可达率；
  - 若某课只有 C、没有 A/B `required`，仍然 warning（或按 spec 定为硬错误）。
- 不允许“把 C 自动升级成 B”来绕过门禁；必须按来源规则判定。

**D. 链接可达性做成两段式。**

- 写课时预检（不阻断生成，记录状态）：
  - `GET`（带 UA、超时、限制大小）；
  - 记录最终 URL、HTTP 状态、内容长度、content-type；
  - 付费墙/登录页启发式：最终域名是出版社、页面含 paywall/login 关键词、
    内容过短、重定向到 `/login` 等，标记 `paywalled`；
  - 预检失败的资源不进入“required”，让模型换一条。
- 定稿前复检：required 资源必须 200 且非付费墙；失败则阻断并给出原因。
- `last_verified` 只写真实检查日期；没检查就留空，不再自动填今天。
- 新增 `tb verify-resources <pack>`（离线默认不跑，显式联网）用于事后复查；
  报告写入 `dist/` 或标准输出，不写学习账本。

**E. 质量指标。**

- 新增“来源类型配比”“required 可达率”“付费墙拦截数”三个指标；
- 论文占比过高给 warning；
- 保留现有 `resource_untrusted_source` / `resource_unsourced` 硬错误。

### 3.4 验收

- 用你的主题新建一个草稿：每个模块至少有 1 条官方文档/标准 + 1 条工程文章；
  自动路由日志显示两类后端都被用到。
- 所有 required 资源：HTTP 200、非付费墙、正文长度达标；`last_verified` 是
  真实检查日期。
- 旧包仍 `tb validate` 0/0；`tb quality` 基线不下降。
- 默认 `pytest` 不联网；搜索/HTTP 全部用假实现测试。

### 3.5 已确认 / 剩余待确认

- 已确认：C 级允许作为补充阅读，每课可多条；`required` 仍只允许 A/B。
- 已确认：论文保留，但不再是默认主角；工程文档/博客占更高配比。
- 剩余：初始“可信工程来源”白名单（ROS/Open Robotics、DDS 厂商、NVIDIA、
  主流机器人公司工程博客、国标/ISO 公开页等）。实现前给一份即可。
- 剩余：补充阅读软上限默认 3 条/课；如果你希望更多，可在 spec 里调。

---

## 4. O4：自动规划课时 + 对话修正方向

### 4.1 现象

- 现在必须手动填“模块数 1–3”“每模块课数 1–5”，系统不根据主题、可投入时间、
  目标级别给建议。
- 大纲一次生成，发现方向不对只能改 HTML 或整份重新生成，没有“边生成边对话”
  的修正过程。

### 4.2 现状

- 新建表单要求手动填模块数、每模块课数、每课检索次数
  （[studio_list.html:10-11](../web/templates/studio_list.html#L10-L11)）。
- 存储层强制 `1–3` 模块、`1–5` 课/模块
  （[store.py:25-26](../src/testbridge/studio/store.py#L25-L26)、
  [store.py:142-149](../src/testbridge/studio/store.py#L142-L149)）。
- 大纲生成严格按这两个数字校验
  （[outline.py:114-120](../src/testbridge/studio/outline.py#L114-L120)），
  提示词只传主题、级别、两个数量
  （[prompts.py:64-72](../src/testbridge/studio/prompts.py#L64-L72)）。
- 页面只有“生成大纲 / 保存大纲 / 重新生成”，没有计划说明，也没有对话
  （[studio_draft.html:12-15](../web/templates/studio_draft.html#L12-L15)）。
- 已有的“大纲 → 调研 → 写课 → 校验 → 定稿”流水线可以直接复用，缺的是
  **计划层**和**修正层**。

### 4.3 推荐方案

**第 1 阶段：确定性课时规划（不依赖 LLM）。**

- 新建草稿时增加输入：
  - 每周可投入小时数（可从 `Goal.weekly_hours` 由用户手填/带入，不直接从
    `learning` import，保持 `studio/` 边界）；
  - 期望周期（周）或目标日期；
  - 学习目的：面试导向 / 项目导向 / 系统补齐；
  - 可选：必须覆盖的主题。
- 计算规则（示例，最终以 spec 为准）：
  - 总学习分钟 = 每周小时 × 60 × 周数 × 利用率（0.6–0.7）；
  - 单课默认 30–45 分钟（按级别调整）；
  - 课数 = clamp(round(总分钟 / 单课分钟), 3, 15)；
  - 模块数 = clamp(ceil(课数 / 5), 1, 3)；
  - 每模块课数 = 均匀分配，余数放到前面的模块。
- 页面展示“建议计划卡片”：模块数、每模块课数、单课分钟、总课时、理由；
  所有数字可手动改。规划是确定性的，不用 LLM 做算术。
- 暂不突破 3 × 5 = 15 课上限；超过 15 课的主题先给出“建议拆成两个包”的提示，
  是否放宽上限单独决策。

**第 2 阶段：对话式修正（LLM 只产出结构化建议）。**

- 新增 `POST /studio/{id}/plan/chat`：
  - 输入：当前计划 + 用户一句话（如“少讲论文，多讲测试实操”“课时减半”）；
  - 输出：`{"plan": {...}, "rationale": "...", "changes": [...]}`；
  - 服务端做确定性校验（模块数/课数上限、概念覆盖、ID 合法），通过后展示
    “改动对比”，用户确认才写入 `draft.json` 的 `plan`。
- 提供快捷意图按钮：更实操 / 更理论 / 减少课时 / 增加项目 / 聚焦某主题；
  也允许自由输入。
- 对话记录只存 `draft.json`（如 `plan_messages`，有上限），不写学习证据。
- 防跑偏：
  - 单次对话最多 N 轮（如 10 轮），历史消息截断；
  - 用户输入按不可信文本处理，长度上限；
  - 模型输出解析失败时保留旧计划并提示，不覆盖；
  - 模型不能直接写文件、不能改 `tb/1` 文件、不能改证据；
  - 计划确认后才生成大纲；已生成大纲后再改计划，必须提示“会重排课程步骤”。
- 第 3 阶段（可选）：把对话扩展到大纲粒度（“第 2 课太浅，改成实操题”），
  仍然只产出结构化修改建议，由用户确认。

### 4.4 验收

- 输入“每周 12 小时、8 周、L3、面试导向”，页面给出带理由的计划
  （例如 3 模块 × 4 课），用户可改数字；确认后大纲严格按计划生成。
- 对话输入“少讲论文，多讲测试实操”后，计划的 `research_queries` 与 objectives
  发生可解释变化；对比页能看到改了什么。
- 模型返回非法 JSON / 超限计划时，旧计划不变，页面显示错误。
- 默认 `pytest` 离线，用假 LLM；旧草稿（无 `plan` 字段）继续可用。

### 4.5 待确认

- 规划输入用“每周小时 + 周期”，还是“目标日期 + 每天分钟”？
- 是否允许突破 15 课上限？建议先不突破，把“拆包”作为提示。
- 对话修正只做到“计划层”，还是一开始就做到“逐课大纲层”？
  建议先计划层，稳定后再往下。

---

## 5. O5：页面排版与样式

### 5.1 现象

页面能用，但排版、层级、状态反馈和移动端体验比较粗糙；学习页与工作台都显得
“工程原型”，不像成品。

### 5.2 现状

- 全站一个 `tb.css`，基础 token 只有 5 个变量
  （[tb.css:1-4](../web/static/tb.css#L1-L4)）。
- 顶栏是一行链接，无移动端折叠
  （[base.html:10-13](../web/templates/base.html#L10-L13)）。
- 阅读区固定 860px；长课没有目录/侧栏；表格在窄屏会溢出；
  工作台状态只有文字（`pending/running/done`），没有进度条或状态色。
- 没有深色模式、`:focus-visible` 样式、减少动画偏好、打印样式。

### 5.3 推荐方案

- **设计 token**：字号阶梯、间距刻度、颜色（含语义色 success/warning/danger）、
  圆角、阴影；统一按钮、表单、卡片、表格、徽章。
- **布局**：响应式顶栏（窄屏折叠）；阅读区限制行宽；长课增加右侧/顶部目录；
  练习区与资源区分组；表格加横向滚动容器。
- **组件**：状态徽章、进度条、步骤卡、提示块（info/warning/error）、
  图注样式、代码块、对比视图（用于 O4 计划 diff 与历史快照）。
- **可访问性**：键盘焦点可见、表单 label 关联、对比度 AA、`prefers-reduced-motion`、
  320px 宽度可用。
- **深色模式**：`prefers-color-scheme`，内联 SVG 用 `currentColor`。
- **工作台**：步骤状态用颜色 + 图标 + 文本，不只靠文字；批量进度可视化。
- 不引入前端框架；继续用 Jinja2 + 原生 CSS/JS；`tb build` 的独立页复用同一套 token。

### 5.4 验收

- 320 / 768 / 1280 三档无横向滚动，导航可用。
- 键盘 Tab 能走完主要操作，焦点可见；颜色对比度达到 AA。
- 深色模式下正文、表格、练习反馈、SVG 图可读。
- 所有页面共用同一套按钮/表单/状态组件；`tb build` 产物样式一致。

### 5.5 待确认

- 深色模式是否现在就要？成本不高，建议一起做。
- 是否需要打印/PDF 样式（把课程打印出来看）？可以作为可选。

---

## 6. 与现有硬规则的关系

| 项 | 触碰点 | 处理方式 |
|---|---|---|
| O1 | “密钥不落盘、不回显、不写日志” | 已确认走方案 A（Windows 用户环境变量），不采用 `.env`，不改边界 |
| O2 第 1 层 | 无契约变更：图就是 HTML + 本地 asset | 直接按 studio 改动做，补测试 |
| O2 第 2 层 | 外部图授权/署名需要存储位置 | 先侧车文件；若要进 manifest，走 spec + 可选字段 |
| O2 第 3 层 | 新增可选 `TESTBRIDGE_IMAGE_*` | 默认关闭；测试用假客户端；密钥规则同 O1 |
| O3 | 质量门禁 trust 语义、来源类型、可达性规则 | 先更新 P3.2/P3.3 spec 与 ROADMAP，再改代码 |
| O4 | 只动 `studio/` 与 `draft.json`；不得 import 引擎模块 | 按创意功能流程：brainstorming + spec + plan |
| O5 | 只动 `web/` 与 `tb.css` | 可直接做；补页面快照/关键元素测试 |

**明确不做：**

- 不做付费墙绕过、不抓取付费内容、不伪造访问状态。
- 不把密钥写进仓库、URL、日志或页面。
- 不为了图引入必需的外部服务；生图默认关闭。
- 不让 LLM 直接改账本、写契约文件；所有写入仍经确定性校验与用户确认。
- 不把 C 级来源静默升级成 A/B 来通过门禁。
- 不引入前端框架或 SPA；保持服务端渲染。

---

## 7. 建议落地顺序

| 步 | 内容 | 产出 | 大概工作量 |
|---|---|---|---|
| 1 | O1 配置一次生效 | `tb env init` / `tb doctor` + README | 0.5–1 天 |
| 2 | O3 参考资料工程化 | spec + 路由分流 + 来源配比 + 可达性预检 | 2–4 天 |
| 3 | O2 第 1 层图 | 图形规格 + SVG 渲染 + 提示词 + 质量 warning | 2–3 天 |
| 4 | O4 计划与对话 | spec + 计划卡片 + 对话修订 | 3–5 天 |
| 5 | O5 样式 | token + 响应式 + 深色模式 + 组件 | 2–3 天，可增量 |

工作量是量级估计，不是承诺；O3/O4 需要先写 spec 再排期。

---

## 8. 决策状态

**已确认（2026-10-26）：**

- **O1**：采用 Windows 用户环境变量 + `tb doctor`；不引入仓库内 `.env`，
  不放宽“密钥不落盘”。
- **O3**：C 级工程博客/社区帖允许作为补充阅读，每课可多条；`required` 仍只
  允许 A/B，C 级不计入 A/B 分子。
- **O2**：先只做确定性 SVG 图；外部图片与 AI 生图暂缓。

**仍待确认（不阻塞 O1 开工）：**

1. **O3**：初始“可信工程来源”白名单（官方文档、标准、厂商博客、开源项目文档）。
2. **O3**：补充阅读软上限默认 3 条/课，是否需要更高？
3. **O4**：规划输入用“每周小时 + 周期”还是“目标日期 + 每天分钟”？是否接受
   暂时维持 15 课上限、超出时建议拆包？对话修正先做到计划层还是逐课大纲层？
4. **O5**：深色模式是否现在一起做？

按 `CLAUDE.md` 的分层流程：O1/O5 可直接做；O2 第 1 层可直接做；
O3/O4 先补 spec 与实施计划。
