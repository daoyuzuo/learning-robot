# TestBridge

内容可替换、证据驱动的技术教学引擎。

## 核心思想

- **内容是数据包，引擎是解释器，能力账本是唯一事实来源。**
- 内容状态（概念、课程、练习、资源）与学习状态（证据、掌握度、复习）分离。
- 确定性核心负责判分、掌握度与调度；AI 只在讲解、开放题辅助和内容起草的边缘。
- “学会了”必须能下钻到证据，不接受手填的掌握度。

## 当前阶段

内容试点已完成（`content-packs/ros2-qos`）；P2.2 增加可选的 AI 追问面板。

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

## 文档

- [总设计](docs/superpowers/specs/2026-10-24-teaching-engine-design.md)
- [P2 学习闭环设计](docs/superpowers/specs/2026-10-25-p2-learning-loop-design.md)
- [P2.2 AI 追问设计](docs/superpowers/specs/2026-10-25-p2.2-tutor-design.md)
- [ROS2 QoS 内容试点](docs/superpowers/specs/2026-10-25-ros2-qos-content-pilot-design.md)
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
