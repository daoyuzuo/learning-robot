# TestBridge

内容可替换、证据驱动的技术教学引擎。

## 核心思想

- **内容是数据包，引擎是解释器，能力账本是唯一事实来源。**
- 内容状态（概念、课程、练习、资源）与学习状态（证据、掌握度、复习）分离。
- 确定性核心负责判分、掌握度与调度；AI 只在讲解、开放题辅助和内容起草的边缘。
- “学会了”必须能下钻到证据，不接受手填的掌握度。

## 当前阶段

P2 学习闭环、P2.1–P2.4 已完成；P3.1 增加内容生产工作台（`/studio`）；P3.2 增加确定性质量门禁（`tb quality`，硬错误阻断定稿）；P3.3 增加 OpenAlex 检索后端与自动路由；P3.4 支持一个包 1–3 个模块、每模块 1–5 课的模块化大纲、顺序批量与单课重写（默认 `pytest` 不联网；真实调用需 `TESTBRIDGE_LIVE=1`）。

## AI 追问（可选）

课程页的追问面板需要一个 OpenAI 兼容端点。未配置时功能自动禁用，不影响其它页面。

```bash
export TESTBRIDGE_LLM_BASE_URL=https://api.deepseek.com/v1
export TESTBRIDGE_LLM_API_KEY=sk-...
export TESTBRIDGE_LLM_MODEL=deepseek-chat
# 可选：export TESTBRIDGE_LLM_TIMEOUT=30
.venv/Scripts/python -m testbridge.cli tutor check
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
练习与资源，不产生重复 ID。批量与单课任务互斥（运行中返回 409），批量不会自动定稿。
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
- [路线图](docs/ROADMAP.md)
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
