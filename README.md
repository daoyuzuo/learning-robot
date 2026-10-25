# TestBridge

内容可替换、证据驱动的技术教学引擎。

## 核心思想

- **内容是数据包，引擎是解释器，能力账本是唯一事实来源。**
- 内容状态（概念、课程、练习、资源）与学习状态（证据、掌握度、复习）分离。
- 确定性核心负责判分、掌握度与调度；AI 只在讲解、开放题辅助和内容起草的边缘。
- “学会了”必须能下钻到证据，不接受手填的掌握度。

## 当前阶段

**P2：学习闭环。**

P1 已完成；P2 在追加式证据之上增加掌握度（规则 + BKT）、FSRS 复习、readiness、每日计划与 Dashboard。

## 文档

- [总设计](docs/superpowers/specs/2026-10-24-teaching-engine-design.md)
- [路线图](docs/ROADMAP.md)
- [开源项目调研](docs/research/ai-teaching-open-source.md)
- [Agent 守则](CLAUDE.md)

## 目标结构（P1）

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

打开 http://127.0.0.1:8000 。
