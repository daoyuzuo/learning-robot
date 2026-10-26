# O3 参考资料工程化与可达性（Design）

- 状态：Implemented，2026-10-26
- 范围：来源类型、按查询路由、C 级补充阅读、OA 优先、链接预检、质量门禁、提示词
- 上游：[优化清单](../../OPTIMIZATION.md)、[P3.3 检索后端](2026-10-25-p3.3-search-backends-design.md)、
  [P3.2 质量门禁](2026-10-25-p3.2-quality-gates-design.md)
- 决策：2026-10-26 确认允许 C 级工程博客/社区帖作为补充阅读，每课可多条；
  `required` 仍只允许 A/B。

---

## 1. 背景与根因

当前资源偏学术、工程来源少，部分链接不可达或落到付费页。根因：

1. `auto` 对“具身智能 / 机器人学习 / 强化学习 / 大模型”等判定为学术，
   整课只走 OpenAlex；DeepSeek 只在无命中/失败时兜底
   （[search_router.py:9-20](../../../src/testbridge/studio/search_router.py#L9-L20)）。
   路由是每课一次，不是按查询分流
   （[web/studio.py:235-244](../../../web/studio.py#L235-L244)）。
2. 写课只允许 A/B 级来源
   （[prompts.py:43-46](../../../src/testbridge/studio/prompts.py#L43-L46)、
   [lessons.py:87-88](../../../src/testbridge/studio/lessons.py#L87-L88)），
   质量门禁对非 A/B 记硬错误
   （[provenance.py:117-129](../../../src/testbridge/quality/provenance.py#L117-L129)）。
   工程博客通常被上游标成 C，被结构性排除。
3. OpenAlex 链接优先 DOI，DOI 常落到出版社付费页
   （[search_openalex.py:44-56](../../../src/testbridge/studio/search_openalex.py#L44-L56)）。
4. 可达性只在定稿时查一次 HTTP 状态
   （[gates.py:61-78](../../../src/testbridge/studio/gates.py#L61-L78)），
   软 404、登录页、付费墙返回 200 时查不出来。
5. `last_verified` 没验证也自动填当天
   （[lessons.py:99-100](../../../src/testbridge/studio/lessons.py#L99-L100)），
   信号失真。
6. 没有来源类型配比规则；`Resource.type` 是自由字符串
   （[models.py:183](../../../src/testbridge/contract/models.py#L183)）。

---

## 2. 目标与非目标

**目标：**

- 每个模块至少 1 条官方文档/标准/仓库和 1 条工程实践来源；论文保留但不再默认占满。
- `auto` 按查询分流，学术查询走 OpenAlex，工程查询走 DeepSeek。
- C 级来源可作为补充阅读，每课可多条；`required` 仍只允许 A/B。
- 给出的链接在写课时和定稿前都经过可达性/付费墙检查。
- `last_verified` 只反映真实检查。

**非目标：**

- 不做付费墙绕过、不抓取付费内容、不伪造访问状态。
- 不新增 SearXNG / Firecrawl / arXiv 适配器。
- 不自动把 C 级来源升级成 A/B。
- 不改判分、掌握度、调度、证据表。
- 默认 `pytest` 不联网。

---

## 3. 内容契约扩展（可选字段）

`Resource` 增加两个可选字段（`tb/1` 只加可选字段，旧包不改也能通过）：

```python
ResourceKind = Literal[
    "official_docs", "standard", "engineering_blog", "tutorial",
    "repository", "paper", "book", "video", "other",
]

class Resource(StrictModel):
    ...
    kind: ResourceKind = "other"
    role: Literal["required", "supplementary"] = "required"
```

规则：

- `required`：`trust` 只能是 A/B；是模块的“必读”来源。
- `supplementary`：允许 A/B/C；D 一律拒绝。
- `role` 缺省为 `required`，`kind` 缺省为 `other`；旧包与旧草稿继续有效。
- 现有 `type` 字段保留，不强制迁移；读取时用 `kind`，缺失时按 `type` 做兼容映射：
  `paper→paper`、`standard/standard_draft→standard`、`docs/documentation→official_docs`、
  `repository→repository`、`article/blog→engineering_blog`、其余 `→other`。
  Pydantic 默认值无法区分“未提供”，因此兼容映射放在 `content/repository.py`
  或 loader 里，用原始 YAML 的字段是否存在判断；`kind` 显式提供时以它为准。
- 校验器新增：`supplementary` 的 C 级允许；D 级始终报错；`required` 的 C 级报错。
  虽然 `tb/1` 只新增了可选字段，`required` + trust C 现在是校验硬错误；随附内容包
  不含 C/D 资源，因此无需迁移。
- `studio/lessons.py::_parse_resources` 同步改为按 `role` 校验：
  `required` 只允许 A/B，`supplementary` 允许 A/B/C；D 一律拒绝。
  旧草稿没有 `role` 时按 `required` 处理。

---

## 4. 调研设计

### 4.1 查询带类型

```python
QueryKind = Literal["academic", "engineering", "official"]

@dataclass(frozen=True)
class ResearchQuery:
    text: str
    kind: QueryKind
```

`build_queries` 从课程大纲的 `research_queries` 与概念标题生成带类型的查询：

- 学术：论文、综述、benchmark、数据集、sim-to-real 等；
- 工程：`best practices`、`tutorial`、`how to`、故障排查、测试方法；
- 官方：`site:docs.ros.org`、`site:github.com`、厂商文档、标准组织页面。

现有 `SITE_QUERY` 保留为 official 模板的一部分。预算仍由
`searches_per_lesson` 控制，按“学术 → 工程 → 官方”轮转取前 N 条，避免全是论文。

### 4.2 按查询路由

`SearchRouter` 增加：

```python
def route_query(self, backend: str, kind: QueryKind, *, topic, titles, domains) -> SearchRoute
```

- 手动 `deepseek` / `openalex`：所有查询都用该后端，**不回退**（保持 P3.3 契约）。
- `auto`：
  - `academic` → OpenAlex，失败/无命中回退 DeepSeek；
  - `engineering` / `official` → DeepSeek，失败/无命中回退 OpenAlex。
- `run_research` 接受 router 而不是单个 provider；逐查询记录
  `{query, kind, backend}` 到档案。
- 去重仍按 URL；同一 URL 被多个查询命中时保留第一次的 kind。

### 4.3 来源分类与信任

新增 `src/testbridge/studio/sources.py`：

```python
def classify_hit(hit: SearchHit) -> ResourceKind: ...
def trust_for_hit(hit: SearchHit) -> str: ...
```

- 先按 URL 域名/路径分类：`docs.*`、`*.readthedocs.io`、`github.com/*/docs` →
  `official_docs`；标准组织域名 → `standard`；`github.com/*` → `repository`；
  DOI / arxiv / openalex `work_type` → `paper`；其余含 blog/tutorial 关键词 →
  `engineering_blog` / `tutorial`。
- 信任：沿用 `TRUST_BY_AUTHORITY`，再叠加**显式域名白名单**：
  - 官方文档、标准组织、主流开源项目文档、维护者工程博客 → 至少 B；
  - 普通社区帖仍为 C；
  - 白名单写在 `sources.py` 常量里，属于作者层确定性规则，不写入内容包。
- 初始白名单（可在评审时增删，不写死到内容包）：

  | 类别 | 域名示例 |
  |---|---|
  | ROS / 机器人 | `docs.ros.org`, `docs.ros2.org`, `design.ros2.org`, `discourse.ros.org`（仅官方公告） |
  | DDS / 标准 | `omg.org`, `dds-foundation.org`, `iso.org`, `iec.ch`, `nist.gov` |
  | 厂商文档 | `docs.nvidia.com`, `developer.nvidia.com`, `docs.openvino.ai` |
  | 开源项目 | `github.com/<project>/docs`, 已知项目的 `readthedocs.io` |
  | 工程博客 | 官方产品博客、维护者博客；普通 Medium/CSDN/知乎默认 C |

  白名单只把命中域名提升到 B，不把内容质量等同于域名；仍需可达性检查。
- 不按“看起来像论文”把 C 升 A；升级只来自域名白名单或 OpenAlex 的 authority。

### 4.4 OpenAlex URL 选择

`SearchHit` 增加可选 `is_oa: bool = False`、`oa_url: str | None = None`。
`OpenAlexSearch` 的 URL 选择改为：

1. `is_oa` 且 `oa_url` 可用 → `oa_url`；
2. `landing_page_url`；
3. DOI URL；
4. 都没有则跳过该 work。

档案保留原始 `doi`、`landing_page_url`、`oa_url`，便于排查。

---

## 5. 可达性检查

新增 `src/testbridge/studio/verify.py`：

```python
@dataclass(frozen=True)
class ResourceCheck:
    url: str
    status: int | None
    final_url: str
    content_length: int
    paywalled: bool
    error: str

def check_url(client, url: str) -> ResourceCheck: ...
```

检查内容：

- `GET`，`timeout=10`，`follow_redirects=True`，限制读取 200KB；
- 状态码、最终 URL、正文长度、content-type；
- 付费墙/登录页启发式：
  - 状态 `401/402/403`；
  - 最终 URL 命中已知出版社/付费域名，或路径含
    `login|signin|subscribe|purchase|paywall`；
  - 正文含 `subscribe to continue`、`purchase this`、`access denied` 等短语；
  - 正文长度低于阈值（如 800 字符）。
- 只做检测，不尝试绕过；`paywalled=True` 即视为不可用。

使用点：

1. **调研阶段**：按来源类型均衡选取至多 10 条命中做预检（每类先取一条，再按原顺序
   补满；可用 `--no-verify` 关闭）；档案记录 `check` 结果；写课提示词只展示
   `paywalled=False` 且 `status<400` 的命中，存在任何检查记录时未检查的命中也不展示。
   关闭预检时不展示 `check` 字段，质量门禁按“未检查”处理（warning，不硬阻断）。
2. **写课解析**：`required` 资源必须来自“已预检且可用”的命中；否则
   `LessonError`，由现有生成重试把错误反馈给模型一次。
3. **定稿前**：`required` 资源重新检查；失败阻断，错误信息带资源 ID 与原因。
4. **事后**：`tb verify-resources <pack>` 重新检查并打印报告；默认不联网，
   显式命令才联网。

`last_verified`：

- 只有检查成功且非付费墙时写入当天日期；
- 检查失败或未检查保持空，不再自动填今天；
- `tb quality` 对 `required` 且为空给 warning；对已过期（超过 180 天）给 warning。

---

## 6. 质量门禁

`quality/provenance.py` 调整：

- 资源循环：
  - `role=required`：
    - `trust` 非 A/B → 现有硬错误 `quality.resource_trust`；
    - 未在档案 A/B 命中 → 现有 `quality.resource_untrusted_source`；
    - 预检 `paywalled` 或 `status>=400` → 新硬错误
      `quality.resource_unreachable`；仅在存在调研档案/预检记录时判定；
      已发布包没有预检记录时退化为 warning，不因缺少记录而阻断；
  - `role=supplementary`：
    - `trust=C` 允许；
    - `trust=D` → 硬错误；
    - 完全不计入 `provenance.trust`（分子与分母都只看 required）；
  - `last_verified` 为空 → warning（required 与 supplementary 都提示）。
- 调整 `provenance.trust`：分母改为 required 资源数，只统计 required 的 A/B；
  supplementary 不参与该指标。
- 新增指标（仅在 `research_dir` 存在、即 `include_metrics=True` 时加入，
  避免已发布包的分数基线变化）：
  - `provenance.source_mix`（5 分）：每课只要至少 1 条 required 资源的 `kind` 属于
    官方/标准/仓库（`official_docs` / `standard` / `repository`）或工程实践
    （`engineering_blog` / `tutorial`）即得分；
  - `provenance.reachable`（5 分）：required 资源可达比例。
- 新增 warning：
  - `quality.supplementary_too_many`：每课 supplementary 超过软上限 3 条；
  - `quality.lesson_only_papers`：某课 required 全是 paper；
  - `quality.lesson_no_ab_required`：某课没有 A/B required；
  - `quality.lesson_no_practice_source`：某课所有资源（required 与 supplementary）
    都不是 `engineering_blog` / `tutorial` / `repository`；只 warning，不扣分。
- 保留 `quality.resource_metadata`（license / last_verified / why 缺失 warning）。

软上限 3 条做成常量 `MAX_SUPPLEMENTARY_PER_LESSON = 3`，可在 spec 评审时调整；
超过只 warning，不阻断。

---

## 7. 提示词

`LESSON_SYSTEM` 的资源段更新：

- 资源字段增加 `kind`、`role`；
- 每课至少 1 条 `role=required` 的 A/B 来源；
- 至少尝试 1 条 `kind` 为 `official_docs` / `standard` / `repository` 的 required；
- 可有 2–3 条 `role=supplementary` 的工程博客/教程；C 级只允许放 supplementary；
- 只引用 `<research>` 中已通过预检的条目；禁止编造 URL；
- `why` 必须写“工程上什么时候用”，不能只写“介绍了……”。

`OUTLINE_SYSTEM` 的 `research_queries` 要求同时包含工程向与官方文档向查询，
避免全是对论文的检索。

prompt 版本：按实施顺序 O3 先落地，`studio/3`。旧草稿继续按 `studio/1` / `studio/2`
显示，不自动迁移。

---

## 8. 兼容与边界

- `tb/1` 只新增可选字段；旧内容包不改也能通过。但 `required` + trust C 是硬错误；
  现有随附包不含 C/D 资源，因此无需迁移。
- 旧草稿没有 `kind` / `role` 时按兼容映射处理；新生成资源写显式字段。
- 手动选择检索后端时不静默回退；只有 `auto` 按查询回退。
- `studio/` 仍不得 import `mastery` / `schedule` / `learning` / `evidence`。
- 不做付费墙绕过；检测到即标记不可用。
- 默认 `pytest` 不联网；搜索、HTTP、模型全部用假实现。

---

## 9. 测试

新增/调整：

| 层 | 覆盖 |
|---|---|
| 契约 | 旧包无 `kind/role` 仍通过；`supplementary` C 允许；D 拒绝；required C 拒绝 |
| 分类 | 官方文档/标准/仓库/论文/博客域名分类；白名单升级 B |
| 路由 | 学术查询走 OpenAlex、工程/官方走 DeepSeek；手动后端不回退；auto 回退 |
| OpenAlex | OA URL 优先；无 OA 时 landing/DOI；缺 URL 跳过 |
| 调研 | 每查询 backend 记录；预检失败的命中不进入模型上下文 |
| 可达性 | 200/404/403/登录跳转/付费墙短语；正文过短 |
| 质量 | required 不可达硬错误；supplementary C 不扣分；软上限 warning；来源配比 |
| 迁移 | 旧草稿资源缺字段仍可写课、定稿 |
| 回归 | 742 个现有测试；两个包 `tb validate` 0/0；`tb quality` 基线 |

验收：

- 新建具身智能测试主题草稿，每模块至少 1 条官方/标准 + 1 条工程来源；
  自动路由记录显示两类后端都被使用。
- 所有 required 资源 `status<400`、非付费墙、`last_verified` 为真实日期。
- 旧包 `tb validate` 0/0；默认 `pytest` 全绿且不联网。
- `tb verify-resources` 对故意放入的死链返回非零退出码。
