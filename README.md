# TestBridge

内容可替换、证据驱动的技术教学引擎。

## 核心思想

- **内容是数据包，引擎是解释器，能力账本是唯一事实来源。**
- 内容状态（概念、课程、练习、资源）与学习状态（证据、掌握度、复习）分离。
- 确定性核心负责判分、掌握度与调度；运行时 AI 只做讲解、开放题辅助和求职/面试辅助。
- 课程创作由编程 AI 通过 `.claude/skills/course-author` 直接写内容包；框架不生成课程。
- “学会了”必须能下钻到证据，不接受手填的掌握度。

## 当前阶段

P2 学习闭环、P2.1–P2.4 已完成；P3.1–P3.5 的框架内生成工作台已退役，课程改为
「编程 AI + course-author skill 直接写 `content-packs/`」；P4.1–P4.3 运行时功能保留。
框架只负责 `tb/1` 契约校验、渲染与学习运行时。默认 `pytest` 不联网；真实 LLM 调用需
`TESTBRIDGE_LIVE=1`。

## 一次性配置模型（Windows）

不需要每个终端重复 `export`。首次运行：

```bash
.venv/Scripts/python -m testbridge.cli env init
```

按提示填写 base URL、model、timeout 和 API key；key 输入不回显、不写入仓库。
确认后写入 Windows 用户级环境变量。该配置供 Tutor/面试/JD 等运行时 AI 使用；
课程创作由编程 AI 自己完成，不依赖这里的模型配置。
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
这是课程创作后的可选检查，不依赖 LLM 或 Studio。

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
3 倍（最多 300 秒）。较长的运行时回答/面试评分可能超过 30 秒，建议：

```bash
export TESTBRIDGE_LLM_TIMEOUT=90
```

回答会标注依据：本课内容 / 包内资源 / 网络来源 / 通用知识。追问记录只存在 `tutor_message` 表，不写入学习证据。

### 联网追问

配置模型服务后，追问默认会检索公开网页并引用来源；面板会显示「联网搜索：已开启 /
已关闭 / 不可用」，可在面板取消「联网搜索」。搜索失败不阻断回答，页面会提示
「本次未获取到网络结果」。涉及“今天/当前日期”的问题使用服务器本地日期，
不依赖搜索结果。搜索沿用 `TESTBRIDGE_LLM_*`，不需要新密钥：

```bash
# 默认开启；设为 0 可全局关闭
export TESTBRIDGE_TUTOR_SEARCH=1
```

引用只接受本次真实返回的 URL；网络来源复用备课的同一套来源分类与信任规则：
优先 A/B，C 仅作补充，D 不使用，页面显示来源可信度。网络内容按不可信输入处理，
不写入证据、掌握度或复习排期。

### 答后讲评

提交任意练习后，反馈区会出现「让 AI 讲讲」。有 rubric 的题型（简答、自评）会附带参考评分，
记为 `llm_review` 证据，标注模型名；它不参与掌握度、复习排期与 readiness。

## 课程创作（Skill）

课程由编程 AI（Claude Code 等）按 skill 直接写 `content-packs/`，框架不生成课程。
项目级 skill 在 `.claude/skills/course-author/SKILL.md`，其中引用：

- `references/content-contract.md`：`tb/1` 文件布局、manifest、题型、资源字段、允许标签
- `references/authoring-guide.md`：教学目标、来源、练习、修订的弱约束

### 新建课程

```bash
# 1. 生成合法空包（确定性脚手架，不调用模型/网络）
tb scaffold my-course --title "课程标题"

# 2. 让编程 AI 读 course-author skill，按主题/大纲/参考资料写 content-packs/my-course

# 3. 校验与运行
tb validate content-packs/my-course
tb quality content-packs/my-course   # 可选建议
tb build content-packs/my-course --out dist
tb serve content-packs/my-course --port 8000 --open
```

- 模块数、课数、单课分钟、难度由 AI 按内容判断，不设框架上限。
- 官方/权威来源由编程 AI 自己的 WebSearch/WebFetch 检索并核验；skill 要求记录真实 URL、
  `license`、`last_verified`，不要把模型记忆当来源。
- 框架只强制 `tb/1` 契约（schema、sanitizer、练习挂载、资源引用）；教学质量是 skill 的弱约束，
  不在框架内强制生成流水线。
- 改 concept/exercise ID 会影响学习证据；skill 会提示影响。旧内容包仍可直接编辑。
- Studio 工作台、草稿、内容演进已移除；删除课程包/草稿直接在文件系统或 git 中处理。

## 内容质量检查（可选）

`tb quality` 是确定性的内容质量检查，不调用 LLM、不生成课程；硬错误退出码 1，
结构无效或参数错误退出码 2，只有警告退出码 0。

```bash
tb quality content-packs/my-course
tb quality content-packs/my-course --json
```

它只是写作建议；交付前必须通过 `tb validate` 的 `tb/1` 契约。

## 学习记录同步到仓库

学习与答题记录写在 `data/testbridge.db`（SQLite，不入库）。同一份状态会镜像到
**可提交的纯文本快照** `data/state/`：

```
data/state/evidence.jsonl   # 一条证据一行，按 (created_at, id) 升序
data/state/goal.json        # 目标角色、每周时长、每日分钟、概念权重
data/state/target-jd.json   # 目标 JD 与权重（存在时）
data/state/manifest.json    # schema、事件数、learner 列表（由内容决定）
```

- `tb serve` 启动时先导入快照，再按证据重建掌握度/复习；此后每次提交练习都会
  自动更新快照。**提交前跑一次 `git add data/state && git commit` 即可跨机同步。**
- 换机器 clone 后直接 `tb serve`，记录自动回来；也可手动一次性导入：
  `tb state-sync --db data/testbridge.db --dir data/state --pack content-packs/my-course`。
- 两台机器各自学习不会互相覆盖：事件按 `id` 幂等并集，`goal` / `target-jd` 按
  `updated_at` 后写者胜；派生状态永远从证据重建。
- 快照目录默认是数据库同级的 `state/`；`TESTBRIDGE_STATE_DIR=<path>` 可改，
  `TESTBRIDGE_STATE_DIR=0` 关闭（回到只有本地数据库的行为）。
- 快照不可写时不影响答题，`/progress` 顶部会提示，答题仍留在数据库里。
- SQLite、`data/artifacts/` 里的产出物、Tutor 对话与投递记录仍然不入库。

```bash
tb state-export --db data/testbridge.db   # 数据库 → 快照
tb state-import --db data/testbridge.db   # 快照 → 数据库
tb state-sync   --db data/testbridge.db --pack content-packs/my-course  # 双向 + 重建
```

## 文档

- [总设计](docs/superpowers/specs/2026-10-24-teaching-engine-design.md)
- [P2 学习闭环设计](docs/superpowers/specs/2026-10-25-p2-learning-loop-design.md)
- [P2.2 AI 追问设计](docs/superpowers/specs/2026-10-25-p2.2-tutor-design.md)
- [Skill 驱动课程创作](docs/superpowers/specs/2026-11-01-skill-based-authoring-design.md)
- [课程作者 Skill](.claude/skills/course-author/SKILL.md)
- [路线图](docs/ROADMAP.md)
- [优化清单（体验债）](docs/OPTIMIZATION.md)
- [开源项目调研](docs/research/ai-teaching-open-source.md)
- [Agent 守则](CLAUDE.md)

## 目标结构

```
content-packs/      # 可替换的内容包（正式课程）
src/testbridge/     # 教学引擎
web/                # 学习界面
tests/              # 契约、运行时、Web 测试；示例包在 tests/fixtures/packs/
data/               # SQLite 与学习者数据（gitignore）；data/state/ 是可提交的快照
dist/               # 单文件课程构建产物（gitignore）
```

## 快速开始

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e ".[dev]"

# 生成合法空包，然后让编程 AI 按 course-author skill 填充内容
python -m testbridge.cli scaffold my-course --title "我的课程"

# 校验内容包
python -m testbridge.cli validate content-packs/my-course

# 构建可离线打开的单文件课程
python -m testbridge.cli build content-packs/my-course --out dist

# 启动学习界面（--open 启动后自动打开浏览器）
python -m testbridge.cli serve content-packs/my-course --port 8000 --open
```

打开 http://127.0.0.1:8000 。还没有课程时，先让 Claude Code 读
`.claude/skills/course-author/SKILL.md` 并按主题生成。

### 学习闭环（P2）

安装后 `tb` 等价于 `python -m testbridge.cli`：

```bash
# 设置学习目标（可重复执行，未指定字段保留原值）
tb goal set --db data/testbridge.db \
  --target-role embodied-ai-test-engineer --weekly-hours 12 --daily-minutes 45

# 从证据重建派生状态（掌握度 / 复习队列）
tb rebuild-state --pack content-packs/my-course --db data/testbridge.db

# 查看 readiness 总分、模块分与门控原因
tb readiness --pack content-packs/my-course --db data/testbridge.db

# 查看今天学什么、为什么、预计时长
tb today --pack content-packs/my-course --db data/testbridge.db
```
