# O1 模型配置一次生效（Design）

- 状态：Implemented，2026-10-26（分支 `p5-optimization`）
- 范围：CLI 配置命令、Windows 用户环境变量写入、离线自检、README
- 上游：[优化清单](../../OPTIMIZATION.md)
- 决策：2026-10-26 确认采用“Windows 用户环境变量 + `tb doctor`”，
  不引入仓库内 `.env`，不放宽“密钥不落盘”。

---

## 1. 背景

当前必需变量为 `TESTBRIDGE_LLM_BASE_URL` / `TESTBRIDGE_LLM_API_KEY` /
`TESTBRIDGE_LLM_MODEL`，可选 `TESTBRIDGE_LLM_TIMEOUT`
（[tutor/config.py:9-15](../../../src/testbridge/tutor/config.py#L9-L15)）。
Web 在启动时只读取一次（[web/app.py:129](../../../web/app.py#L129)），
每个新终端都要重新 `export`；`TESTBRIDGE_LLM_TIMEOUT` 默认 30 秒，
生成整节课经常不够，临时调高又只对当前终端有效。

目标：**一次配置，之后每个新终端和 Web 服务自动继承**，同时不把密钥写进
仓库、日志或页面。

---

## 2. 非目标

- 不实现仓库内 `.env`、不实现项目级配置文件。
- 不引入 `python-dotenv` 或 keyring。
- 不自动重启正在运行的 Web 服务。
- 不在默认测试中读取真实环境变量或访问网络。
- 不改变 `TutorConfig` 的读取契约：仍然只从 `TESTBRIDGE_LLM_*` 读取。

---

## 3. 命令设计

### 3.1 `tb env init`

交互式写入用户级环境变量。

```text
tb env init [--dry-run] [--base-url URL] [--model NAME] [--timeout SECONDS]
```

行为：

1. 读取当前进程已有的 `TESTBRIDGE_LLM_*` 作为默认值。
2. 缺少的项逐项询问：
   - base URL：校验 `http://` 或 `https://`；
   - model：非空；
   - timeout：浮点，`> 0`，默认 90 秒（内容生成建议值）；
   - API key：用 `getpass` 输入，不回显；**不接受命令行参数**，避免进入
     shell history。
3. 打印将要写入的变量名与非敏感值；API key 只显示 `set (N chars)`。
4. 要求输入 `yes` 确认后写入；`--dry-run` 只打印，不写。
5. 写入完成后提示：“请重开终端；已运行的 Web 服务需要重启”。

平台行为：

- **Windows**：写 `HKEY_CURRENT_USER\Environment`，值为 `REG_SZ`；
  写完后广播 `WM_SETTINGCHANGE`，让新进程继承。
- **POSIX**：不自动改 shell 配置；打印可直接复制的 `export` 行，
  由用户放进 `~/.profile` / `~/.zshrc`。这样不在磁盘上留下由程序管理的密钥文件。

安全性：

- 任何输出、异常、日志都不得包含 API key。
- 写入失败时只报变量名和错误类型，不回显值。
- 不把变量写进仓库目录、`data/`、`drafts/` 或任何内容包。

### 3.2 `tb doctor`

离线自检，退出码可用于脚本。

```text
tb doctor [--probe]
```

默认输出：

```text
llm.base_url   set   https://api.deepseek.com
llm.model      set   deepseek-chat
llm.timeout    set   90s
llm.api_key    set   (32 chars)
openalex.mailto unset
openalex.base_url default https://api.openalex.org
openalex.timeout default 10s
```

规则：

- 必需项缺失时退出码 `2`；齐全时 `0`。
- base URL 只显示 scheme + host，不显示路径/查询串（避免泄露内部网关）。
- API key 只显示“set (N chars)”或“missing”，绝不显示内容。
- `--probe` 才调用一次模型连通性检查，复用 `tutor check` 的超时与错误处理；
  默认完全离线。
- 不读取 `.env`，不修改环境。

### 3.3 可选：`tb env show`

不单独做；`tb doctor` 已覆盖“当前进程读到了什么”。如果后续需要机器可读输出，
再加 `--json`，不进入本轮。

---

## 4. 代码结构

新增 `src/testbridge/tutor/env_store.py`：

```python
class EnvWriter(Protocol):
    def set_user_env(self, values: Mapping[str, str]) -> None: ...

class WindowsUserEnv:
    """Write HKCU\\Environment and broadcast WM_SETTINGCHANGE."""

def write_user_env(values: Mapping[str, str], *, writer: EnvWriter | None = None) -> None:
    ...
```

- Windows 实现使用标准库 `winreg` + `ctypes`；不新增依赖。
- 测试注入假 `EnvWriter`，不碰真实注册表。
- POSIX 实现返回 `NotImplementedError`，由 CLI 打印 export 行。

`cli.py` 增加：

- `env` 子命令（`init`）；
- `doctor` 子命令；
- 两个命令都只做参数解析与输出，业务逻辑放 `env_store.py`。

`doctor` 不依赖 `web`，可直接从 `tutor.config` 读取。

---

## 5. 错误与边界

| 情况 | 行为 |
|---|---|
| 用户取消确认 | 退出码 1，不写任何变量 |
| URL 非法 / timeout ≤ 0 | 打印具体字段错误，退出码 2，不写 |
| 写入注册表失败 | 打印失败变量名，退出码 2，不写值 |
| `doctor` 缺必需项 | 列出缺失项，退出码 2 |
| `doctor --probe` 网络失败 | 打印错误类型，退出码 2；不影响默认离线检查 |
| 运行中的 Web 服务 | 不自动重启；提示用户重启 |

---

## 6. 测试

新增 `tests/test_env_commands.py`：

- `tb env init --dry-run` 不调用 writer，输出不含 key。
- 交互输入完整时写入 4 个变量；fake writer 收到正确键值。
- 取消确认不写入。
- 非法 URL / timeout 被拒绝。
- Windows writer 的注册表写入用 fake 模块/对象验证（不访问真实注册表）。
- `tb doctor` 在缺失/齐全时的输出与退出码。
- `tb doctor --probe` 用假客户端验证成功/失败路径。
- 所有测试 monkeypatch 环境变量，不依赖宿主真实配置。

回归：

- `pytest` 全绿，现有 742 个测试不回归。
- `tb tutor check` 行为不变。
- 不新增 live 测试。

---

## 7. 验收

- 新开终端、不执行 `export`，`tb doctor` 显示配置齐全；`tb serve` 后 Studio
  能调用模型。
- `TESTBRIDGE_LLM_TIMEOUT` 一次设为 90 秒，新终端与 Web 进程都读到 90。
- 页面、日志、异常、`doctor` 输出中都不出现 API key。
- `tb env init --dry-run` 可安全演示。
- README 有 Windows 一次性配置段，写明“重开终端 / 重启服务”。

---

## 8. 实施顺序

1. `env_store.py` + fake writer 测试。
2. `tb env init`。
3. `tb doctor`（先离线，再加 `--probe`）。
4. README 与 ROADMAP 更新。
5. 全量测试与手工验收。
