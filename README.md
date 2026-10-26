# TestBridge

内容可替换、证据驱动的技术教学引擎。

## 核心思想

- **内容是数据包，引擎是解释器，能力账本是唯一事实来源。**
- 内容状态（概念、课程、练习、资源）与学习状态（证据、掌握度、复习）分离。
- 确定性核心负责判分、掌握度与调度；AI 只在讲解、开放题辅助和内容起草的边缘。
- “学会了”必须能下钻到证据，不接受手填的掌握度。

## 当前阶段

P2 学习闭环、P2.1–P2.4 已完成；P3.1 增加内容生产工作台（`/studio`）；P3.2 增加确定性质量门禁（`tb quality`，硬错误阻断定稿）；P3.3 增加 OpenAlex 检索后端与自动路由；P3.4 支持一个包 1–3 个模块、每模块 1–5 课的模块化大纲、顺序批量与单课重写；P3.5 增加跨草稿内容演进（`/studio/evolution`、prompt 版本、旧/新快照对比）。默认 `pytest` 不联网；真实调用需 `TESTBRIDGE_LIVE=1`。

## 一次性配置模型（Windows）

不需要每个终端重复 `export`。首次运行：

```bash
.venv/Scripts/python -m testbridge.cli env init
```

按提示填写 base URL、model、timeout（内容生成建议 90 秒）和 API key；
key 输入不回显、不写入仓库。确认后写入 Windows 用户级环境变量。
**重开终端；已运行的 Web 服务需要重启。**

检查当前终端读到的配置（不会显示 key）：

```bash
.venv/Scripts/python -m testbridge.cli doctor
```

需要联网自检时加 `--probe`；默认离线。

## 复查资源链接（可选，联网）

```bash
PYTHONPATH=src .venv/Scripts/python -m testbridge.cli verify-resources content-packs/<pack>
```

（本机 venv 未安装 `testbridge` 包时命令需 `PYTHONPATH=src`；安装后可直接用 `tb`。）

required 资源的死链或付费墙会返回退出码 1；补充阅读失败只提示，不阻断。
Studio 调研时默认会对按来源类型均衡选取的至多 10 条命中做链接预检。
`TESTBRIDGE_STUDIO_VERIFY=0` 只关闭链接预检，搜索与模型调用不受影响。

## AI 追问（可选）

课程页的追问面板需要一个 OpenAI 兼容端点。未配置时功能自动禁用，不影响其它页面。

```bash
export TESTBRIDGE_LLM_BASE_URL=https://api.deepseek.com/v1
export TESTBRIDGE_LLM_API_KEY=sk-...
export TESTBRIDGE_LLM_MODEL=deepseek-chat
# 可选：export TESTBRIDGE_LLM_TIMEOUT=30
.venv/Scripts/python -m testbridge.cli tutor check
```

请求遇到超时、连接错误或 `429/5xx` 时会自动重试一次；超时重试把截止时间延长到
3 倍（最多 300 秒）。生成整节课通常超过 30 秒，使用 Studio 时建议：

```bash
export TESTBRIDGE_LLM_TIMEOUT=90
```

回答会标注依据：本课内容 / 包内资源 / 通用知识。追问记录只存在 `tutor_message` 表，不写入学习证据。

### 答后讲评

提交任意练习后，反馈区会出现「让 AI 讲讲」。有 rubric 的题型（简答、自评）会附带参考评分，
记为 `llm_review` 证据，标注模型名；它不参与掌握度、复习排期与 readiness。

## 内容工作台（P3.1–P3.4）

启动 Web 后打开 http://127.0.0.1:8000/studio ：

1. 新建草稿（主题 / 级别 / 模块数 1–3 / 每模块课数 1–5 / 每课检索次数 / 检索源）
2. 直接编辑大纲（HTML）：可改模块标题、模块概念与课程归属；保存后重写 `module.yaml`
3. 按课调研（OpenAlex / DeepSeek Search，可自动路由），或点「全部调研」顺序跑完所有待办课
4. 按课写课，或点「全部写课」顺序跑完所有待办课；已完成的课显示「重写这一课」
5. 校验（离线 validate + 资源可达性）
6. 定稿到 `content-packs/`

「全部调研 / 全部写课」只跑 `pending` / `failed` 的课，按模块与课的顺序串行执行；
单课失败不中断后续课，批量结束时汇总为 `failed`。已完成的课用「重写这一课」替换旧的
练习与资源，不产生重复 ID。模型在多节课复用同一练习/资源 ID 时，写盘会自动加课程前缀
（如 `L-002-001-EX-1`），并同步正文里的 `data-tb-exercise` / `data-tb-resource`。
批量与单课任务互斥（运行中返回 409），批量不会自动定稿。
旧草稿（单模块、扁平 outline、无模块字段）仍按单模块 `M01` 继续可用。

草稿在 `drafts/`（已 gitignore）；密钥仍走 `TESTBRIDGE_LLM_*` 环境变量。
真实调用的测试需显式开启：

```bash
TESTBRIDGE_LIVE=1 .venv/Scripts/python -m pytest -m live
```

## 检索后端（P3.3）

新建草稿时可选择检索源：

- `auto`（默认）：学术主题走 OpenAlex，文档主题走 DeepSeek Search；首选无命中或失败时回退。
- `deepseek`：只查 DeepSeek，不回退。
- `openalex`：只查 OpenAlex，不回退。

OpenAlex 本身无需 API key；但 Studio 的调研页仍要求启用 `TESTBRIDGE_LLM_*`（DeepSeek Search 与写课）。可选环境变量：

```bash
export TESTBRIDGE_OPENALEX_MAILTO=you@example.com   # polite pool
# export TESTBRIDGE_OPENALEX_BASE_URL=https://api.openalex.org
# export TESTBRIDGE_OPENALEX_TIMEOUT=10
```

OpenAlex 可信度：期刊/会议/书籍章节/review 记 A，预印本记 B，其他记 C，撤稿记 D。
当存在调研档案时，资源必须来自 A/B 命中才能通过质量门禁。

## 内容演进（P3.5）

改了提示词之后，用 http://127.0.0.1:8000/studio/evolution 判断已有草稿要不要重写、重写后是否更好：

1. 页面按草稿分组列出模块/课程、课程状态与当前 prompt 版本；可跨草稿勾选课程。
2. 「开始重生成」把选中课程放进一个后台任务：按草稿分组、组内按大纲顺序串行重写。
3. 每课重写前把旧的 HTML / 练习 / 资源存为快照：
   `drafts/<id>/history/<lesson_id>/<UTC 时间戳>.json`（目录已 gitignore）。
4. 重写后记录练习数、题型、级别、资源数、资源可信度、HTML 与 prompt 版本变化：结果页展示
   练习/资源数与整包质量分 delta，级别与资源可信度在历史页对比。
5. 页面显示每个草稿的整包质量分**前后与 delta**，以及逐课失败原因。
6. 每课有历史页 `/studio/<id>/history/<lesson_id>`：只读展示“最近一次与当前内容不同的快照
   vs 当前内容”的摘要；若快照与当前一致会明确标注。不渲染完整 HTML，不提供恢复按钮。

版本记录：新生成的课程写 `studio/2`；没有该字段的旧草稿按 `studio/1` 处理。版本随课程记录在
`draft.json` 的 `steps.lessons[<id>].prompt_version`，因此同一草稿可能混有不同版本。
升级只做记录与对比，不自动迁移、不自动重写旧草稿。

失败与并发：单课失败不影响其它课/草稿；目标草稿有运行中的批量或单课任务时，该草稿整组失败；
进化任务运行中再启动会返回 409。报告写入 `drafts/<id>/history/evolution-<时间戳>.json`；
任务状态只在内存，重启后历史快照与报告仍在，但任务需重跑。

**不做：** `tb migrate`、完整行级 HTML/YAML diff、快照回滚、重生成已发布 `content-packs/`、
取消运行中的进化任务。

## 质量门禁（P3.2）

```bash
# 已发布包：结构类检查（无调研档案，分数按结构项归一）
tb quality content-packs/sample-sensors

# 草稿：自动读取 draft.json 与 research/，做完整检查
tb quality drafts/<id>

# 输出 JSON；显式指定档案与预算
tb quality drafts/<id> --research-dir drafts/<id>/research --budget 20 --json
```

有硬错误退出码 1；内容包结构无效、或显式指定的 `--research-dir` 不存在、或 `--budget` 小于 1 时退出码 2；只有警告退出码 0。
`force` 与 `skip_verify` 都不能绕过质量门禁。

## 文档

- [总设计](docs/superpowers/specs/2026-10-24-teaching-engine-design.md)
- [P2 学习闭环设计](docs/superpowers/specs/2026-10-25-p2-learning-loop-design.md)
- [P2.2 AI 追问设计](docs/superpowers/specs/2026-10-25-p2.2-tutor-design.md)
- [ROS2 QoS 内容试点](docs/superpowers/specs/2026-10-25-ros2-qos-content-pilot-design.md)
- [P3.2 质量门禁设计](docs/superpowers/specs/2026-10-25-p3.2-quality-gates-design.md)
- [P3.3 检索后端设计](docs/superpowers/specs/2026-10-25-p3.3-search-backends-design.md)
- [P3.4 多模块与批量设计](docs/superpowers/specs/2026-10-25-p3.4-multi-module-batch-design.md)
- [P3.5 内容演进设计](docs/superpowers/specs/2026-10-26-p3.5-content-evolution-design.md)
- [路线图](docs/ROADMAP.md)
- [优化清单（体验债）](docs/OPTIMIZATION.md)
- [开源项目调研](docs/research/ai-teaching-open-source.md)
- [Agent 守则](CLAUDE.md)

## 目标结构

```
content-packs/      # 可替换的内容包
src/testbridge/     # 教学引擎
web/                # 学习界面
tests/              # 契约、运行时、Web 测试
data/               # SQLite 与学习者数据（gitignore）
dist/               # 单文件课程构建产物（gitignore）
```

## 快速开始

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e ".[dev]"

# 校验内容包
python -m testbridge.cli validate content-packs/sample-sensors

# 构建可离线打开的单文件课程
python -m testbridge.cli build content-packs/sample-sensors --out dist

# 启动学习界面
python -m testbridge.cli serve content-packs/sample-sensors --port 8000
```

打开 http://127.0.0.1:8000 。

### 学习闭环（P2）

安装后 `tb` 等价于 `python -m testbridge.cli`：

```bash
# 设置学习目标（可重复执行，未指定字段保留原值）
tb goal set --db data/testbridge.db \
  --target-role embodied-ai-test-engineer --weekly-hours 12 --daily-minutes 45

# 从证据重建派生状态（掌握度 / 复习队列）
tb rebuild-state --pack content-packs/sample-sensors --db data/testbridge.db

# 查看 readiness 总分、模块分与门控原因
tb readiness --pack content-packs/sample-sensors --db data/testbridge.db

# 查看今天学什么、为什么、预计时长
tb today --pack content-packs/sample-sensors --db data/testbridge.db
```
