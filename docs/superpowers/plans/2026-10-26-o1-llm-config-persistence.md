# O1 模型配置一次生效 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `TESTBRIDGE_LLM_*` 在 Windows 用户级环境变量中一次配置，之后新终端与服务自动继承；提供 `tb env init` 与 `tb doctor`。

**Architecture:** 新增 `tutor/env_store.py` 负责平台相关的用户环境写入与展示辅助；`cli.py` 只做参数解析、交互与输出。密钥只从环境变量读取，不写仓库、不回显。测试全部注入假 writer / 假客户端，不碰真实注册表与环境。

**Tech Stack:** Python 3.10+、标准库 `winreg` / `ctypes` / `getpass` / `urllib.parse`、argparse、pytest。

**Spec:** `docs/superpowers/specs/2026-10-26-o1-llm-config-persistence-design.md`

## Global Constraints

- 不新增第三方依赖。
- 密钥不得出现在 stdout、stderr、异常、日志、任何文件中。
- 默认 `pytest` 不联网、不读取真实用户环境变量。
- 现有 742 个测试不得回归。
- Windows 用户环境写入用 `HKEY_CURRENT_USER\Environment` + `WM_SETTINGCHANGE`；
  POSIX 只打印 `export` 行，不自动改 shell 配置。
- 修改环境后必须提示“重开终端 / 重启 Web 服务”。

---

## File Structure

- Create: `src/testbridge/tutor/env_store.py` — 用户环境写入、URL 展示、export 行生成。
- Modify: `src/testbridge/cli.py` — 增加 `doctor` 与 `env init` 子命令及处理分支。
- Create: `tests/test_env_commands.py` — 交互、写入、doctor、probe 测试。
- Modify: `README.md` — Windows 一次性配置说明。

---

### Task 1: 环境写入模块与展示辅助

**Files:**
- Create: `src/testbridge/tutor/env_store.py`
- Test: `tests/test_env_commands.py`

**Interfaces:**
- Produces:
  - `class EnvWriteError(Exception)`
  - `class EnvWriter(Protocol): def set_user_env(self, values: Mapping[str, str]) -> None`
  - `class WindowsUserEnv`（实现 `EnvWriter`）
  - `def write_user_env(values: Mapping[str, str], *, writer: EnvWriter | None = None) -> None`
  - `def export_lines(values: Mapping[str, str]) -> list[str]`
  - `def display_url(url: str) -> str`
  - `def secret_status(value: str | None) -> str`

- [x] **Step 1: Write the failing tests**

```python
# tests/test_env_commands.py
from testbridge.tutor.env_store import (
    EnvWriteError,
    export_lines,
    display_url,
    secret_status,
    write_user_env,
)


class FakeWriter:
    def __init__(self) -> None:
        self.values = None

    def set_user_env(self, values):
        self.values = dict(values)


def test_write_user_env_uses_injected_writer() -> None:
    writer = FakeWriter()
    write_user_env({"TESTBRIDGE_LLM_MODEL": "demo"}, writer=writer)
    assert writer.values == {"TESTBRIDGE_LLM_MODEL": "demo"}


def test_export_lines_quote_values() -> None:
    lines = export_lines({"TESTBRIDGE_LLM_MODEL": "demo model"})
    assert lines == ['export TESTBRIDGE_LLM_MODEL="demo model"']


def test_display_url_hides_path_and_query() -> None:
    assert display_url("https://api.example.com/v1?token=secret") == (
        "https://api.example.com"
    )


def test_display_url_keeps_port() -> None:
    assert display_url("http://127.0.0.1:8080/v1") == "http://127.0.0.1:8080"


def test_display_url_rejects_missing_host() -> None:
    assert display_url("not-a-url") == "(invalid)"


def test_secret_status_never_returns_value() -> None:
    assert secret_status("sk-secret") == "set (9 chars)"
    assert secret_status("") == "missing"
    assert secret_status(None) == "missing"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_env_commands.py -v`
Expected: FAIL with `ModuleNotFoundError: testbridge.tutor.env_store`

- [x] **Step 3: Write minimal implementation**

```python
# src/testbridge/tutor/env_store.py
"""Write one-time user environment configuration.

The module never logs or returns secret values. Tests inject a fake writer so
they do not touch the real Windows registry.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Protocol
from urllib.parse import urlsplit


class EnvWriteError(Exception):
    """The user environment could not be written."""


class EnvWriter(Protocol):
    def set_user_env(self, values: Mapping[str, str]) -> None: ...


class WindowsUserEnv:
    """Write HKCU\\Environment and notify new processes."""

    def set_user_env(self, values: Mapping[str, str]) -> None:
        if os.name != "nt":
            raise EnvWriteError("Windows user environment is only available on Windows")
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
            ) as key:
                for name, value in values.items():
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        except OSError as exc:
            raise EnvWriteError(type(exc).__name__) from None
        _broadcast_environment_change()


def _broadcast_environment_change() -> None:
    import ctypes

    hwnd_broadcast = 0xFFFF
    wm_settingchange = 0x001A
    smto_abortifhung = 0x0002
    result = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(
        hwnd_broadcast,
        wm_settingchange,
        0,
        "Environment",
        smto_abortifhung,
        5000,
        ctypes.byref(result),
    )


def write_user_env(
    values: Mapping[str, str], *, writer: EnvWriter | None = None
) -> None:
    selected = writer or WindowsUserEnv()
    selected.set_user_env(dict(values))


def export_lines(values: Mapping[str, str]) -> list[str]:
    return [
        f'export {name}="{str(value).replace(chr(34), chr(92) + chr(34))}"'
        for name, value in values.items()
    ]


def display_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return "(invalid)"
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return "(invalid)"
    host = parts.hostname
    if port:
        host = f"{host}:{port}"
    return f"{parts.scheme}://{host}"


def secret_status(value: str | None) -> str:
    return f"set ({len(value)} chars)" if value else "missing"
```

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_env_commands.py -v`
Expected: PASS（6 passed）

- [x] **Step 5: Commit**

```bash
git add src/testbridge/tutor/env_store.py tests/test_env_commands.py
git commit -m "feat: add user environment writer helpers"
```

---

### Task 2: `tb env init` 交互与写入

**Files:**
- Modify: `src/testbridge/cli.py`
- Test: `tests/test_env_commands.py`

**Interfaces:**
- Consumes: `write_user_env`, `export_lines`, `EnvWriteError` from Task 1.
- Produces:
  - `main(["env", "init", ...]) -> int`
  - 交互输入：base URL、model、timeout、API key；`--dry-run` 不写。

- [x] **Step 1: Write the failing tests**

```python
# append to tests/test_env_commands.py
import getpass

import pytest

from testbridge.cli import main


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch):
    for name in (
        "TESTBRIDGE_LLM_BASE_URL",
        "TESTBRIDGE_LLM_API_KEY",
        "TESTBRIDGE_LLM_MODEL",
        "TESTBRIDGE_LLM_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_env_init_dry_run_masks_key(monkeypatch, capsys) -> None:
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "sk-secret")
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    code = main([
        "env", "init", "--dry-run",
        "--base-url", "https://api.example.com/v1",
        "--model", "demo",
        "--timeout", "90",
    ])

    captured = capsys.readouterr()
    assert code == 0
    assert "sk-secret" not in captured.out
    assert "TESTBRIDGE_LLM_API_KEY" in captured.out
    assert "set (9 chars)" in captured.out


def test_env_init_writes_via_injected_writer(monkeypatch, capsys) -> None:
    written = {}

    def fake_write(values):
        written.update(values)

    monkeypatch.setattr("testbridge.cli.write_user_env", fake_write)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "sk-secret")
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    code = main([
        "env", "init",
        "--base-url", "https://api.example.com/v1",
        "--model", "demo",
        "--timeout", "90",
    ])

    assert code == 0
    assert written == {
        "TESTBRIDGE_LLM_BASE_URL": "https://api.example.com/v1",
        "TESTBRIDGE_LLM_API_KEY": "sk-secret",
        "TESTBRIDGE_LLM_MODEL": "demo",
        "TESTBRIDGE_LLM_TIMEOUT": "90",
    }
    assert "sk-secret" not in capsys.readouterr().out


def test_env_init_cancel_does_not_write(monkeypatch, capsys) -> None:
    called = False

    def fake_write(values):
        nonlocal called
        called = True

    monkeypatch.setattr("testbridge.cli.write_user_env", fake_write)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "sk-secret")
    monkeypatch.setattr("builtins.input", lambda prompt: "" if "yes" in prompt else "n")

    code = main([
        "env", "init",
        "--base-url", "https://api.example.com/v1",
        "--model", "demo",
        "--timeout", "90",
    ])

    assert code == 1
    assert called is False


def test_env_init_rejects_bad_url(monkeypatch, capsys) -> None:
    written = {}
    monkeypatch.setattr(
        "testbridge.cli.write_user_env",
        lambda values: written.update(values),
    )
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "sk-secret")

    code = main([
        "env", "init",
        "--base-url", "ftp://api.example.com",
        "--model", "demo",
        "--timeout", "90",
    ])

    assert code == 2
    assert written == {}
    assert "base URL" in capsys.readouterr().err
```

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_env_commands.py -v`
Expected: FAIL because `main(["env", ...])` is not implemented.

- [x] **Step 3: Write minimal implementation**

In `src/testbridge/cli.py`:

```python
import getpass
import os

from testbridge.tutor.env_store import (
    EnvWriteError,
    display_url,
    export_lines,
    secret_status,
    write_user_env,
)

REQUIRED_LLM_VARS = (
    "TESTBRIDGE_LLM_BASE_URL",
    "TESTBRIDGE_LLM_API_KEY",
    "TESTBRIDGE_LLM_MODEL",
)


def _valid_base_url(value: str) -> bool:
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return False
    return parts.scheme in {"http", "https"} and bool(parts.hostname)


def _prompt_value(label: str, current: str, *, secret: bool = False) -> str:
    suffix = f" [{secret_status(current) if secret else current}]" if current else ""
    prompt = f"{label}{suffix}: "
    value = (
        getpass.getpass(prompt)
        if secret
        else input(prompt)
    ).strip()
    return value or current


def _cmd_env_init(args) -> int:
    current = {name: os.environ.get(name, "") for name in REQUIRED_LLM_VARS}
    base_url = args.base_url or _prompt_value(
        "TESTBRIDGE_LLM_BASE_URL", current["TESTBRIDGE_LLM_BASE_URL"]
    )
    model = args.model or _prompt_value(
        "TESTBRIDGE_LLM_MODEL", current["TESTBRIDGE_LLM_MODEL"]
    )
    timeout = args.timeout or _prompt_value(
        "TESTBRIDGE_LLM_TIMEOUT", os.environ.get("TESTBRIDGE_LLM_TIMEOUT", "")
    ) or "90"
    api_key = _prompt_value(
        "TESTBRIDGE_LLM_API_KEY", current["TESTBRIDGE_LLM_API_KEY"], secret=True
    )

    if not _valid_base_url(base_url):
        print("ERROR env: base URL must start with http:// or https://", file=sys.stderr)
        return 2
    if not model:
        print("ERROR env: model must not be empty", file=sys.stderr)
        return 2
    try:
        timeout_value = float(timeout)
    except ValueError:
        timeout_value = 0
    if timeout_value <= 0:
        print("ERROR env: timeout must be > 0", file=sys.stderr)
        return 2
    if not api_key:
        print("ERROR env: API key must not be empty", file=sys.stderr)
        return 2

    values = {
        "TESTBRIDGE_LLM_BASE_URL": base_url,
        "TESTBRIDGE_LLM_API_KEY": api_key,
        "TESTBRIDGE_LLM_MODEL": model,
        "TESTBRIDGE_LLM_TIMEOUT": timeout,
    }
    print("will set:")
    for name, value in values.items():
        shown = secret_status(value) if name == "TESTBRIDGE_LLM_API_KEY" else value
        print(f"  {name} = {shown}")

    if args.dry_run:
        return 0
    answer = input("write these to your user environment? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        print("cancelled")
        return 1
    if os.name != "nt":
        print("add these lines to your shell profile, then restart the shell:")
        for line in export_lines(values):
            print(line)
        return 0
    try:
        write_user_env(values)
    except EnvWriteError as exc:
        print(f"ERROR env: could not write user environment: {exc}", file=sys.stderr)
        return 2
    print("saved. reopen your terminal and restart any running Web service.")
    return 0
```

Add subparsers in `main` before `args = parser.parse_args(argv)`:

```python
doctor = sub.add_parser("doctor", help="check local configuration")
doctor.add_argument("--probe", action="store_true")

env = sub.add_parser("env", help="manage user-level configuration")
env_sub = env.add_subparsers(dest="env_command", required=True)
env_init = env_sub.add_parser("init", help="write TESTBRIDGE_LLM_* once")
env_init.add_argument("--base-url", default=None)
env_init.add_argument("--model", default=None)
env_init.add_argument("--timeout", default=None)
env_init.add_argument("--dry-run", action="store_true")
```

Add dispatch branches after `args = parser.parse_args(argv)`:

```python
if args.command == "env":
    if args.env_command == "init":
        return _cmd_env_init(args)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_env_commands.py -v`
Expected: PASS（10 passed）

- [x] **Step 5: Commit**

```bash
git add src/testbridge/cli.py tests/test_env_commands.py
git commit -m "feat: add tb env init"
```

---

### Task 3: `tb doctor` 离线自检

**Files:**
- Modify: `src/testbridge/cli.py`
- Test: `tests/test_env_commands.py`

**Interfaces:**
- Consumes: `display_url`, `secret_status`, `load_config`, `missing_vars`.
- Produces: `main(["doctor"]) -> 0 | 2`；`main(["doctor", "--probe"])` 复用模型客户端。

- [x] **Step 1: Write the failing tests**

```python
# append to tests/test_env_commands.py
def test_doctor_reports_missing(monkeypatch, capsys) -> None:
    code = main(["doctor"])
    out = capsys.readouterr().out
    assert code == 2
    assert "TESTBRIDGE_LLM_BASE_URL" in out
    assert "missing" in out


def test_doctor_masks_key(monkeypatch, capsys) -> None:
    monkeypatch.setenv("TESTBRIDGE_LLM_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("TESTBRIDGE_LLM_API_KEY", "sk-secret")
    monkeypatch.setenv("TESTBRIDGE_LLM_MODEL", "demo")
    monkeypatch.setenv("TESTBRIDGE_LLM_TIMEOUT", "90")

    code = main(["doctor"])
    out = capsys.readouterr().out
    assert code == 0
    assert "sk-secret" not in out
    assert "https://api.example.com" in out
    assert "/v1" not in out
    assert "set (9 chars)" in out


def test_doctor_probe_reports_reply(monkeypatch, capsys) -> None:
    monkeypatch.setenv("TESTBRIDGE_LLM_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("TESTBRIDGE_LLM_API_KEY", "sk-secret")
    monkeypatch.setenv("TESTBRIDGE_LLM_MODEL", "demo")

    class FakeClient:
        def complete(self, system: str, user: str) -> str:
            return "ok"

    monkeypatch.setattr("testbridge.cli.build_tutor_client", lambda config: FakeClient())
    code = main(["doctor", "--probe"])
    out = capsys.readouterr().out
    assert code == 0
    assert "latency" in out
    assert "ok" in out
    assert "sk-secret" not in out


def test_doctor_probe_missing_config(monkeypatch, capsys) -> None:
    code = main(["doctor", "--probe"])
    assert code == 2
    assert "missing" in capsys.readouterr().err
```

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_env_commands.py -v`
Expected: FAIL because `doctor` is not implemented.

- [x] **Step 3: Write minimal implementation**

Add to `cli.py`:

```python
def _cmd_doctor(args) -> int:
    required = [
        ("llm.base_url", "TESTBRIDGE_LLM_BASE_URL", display_url),
        ("llm.model", "TESTBRIDGE_LLM_MODEL", str),
        ("llm.api_key", "TESTBRIDGE_LLM_API_KEY", secret_status),
    ]
    missing = []
    for label, name, formatter in required:
        value = os.environ.get(name, "")
        if not value:
            missing.append(name)
            print(f"{label:16} missing  {name}")
            continue
        print(f"{label:16} set      {formatter(value)}")

    timeout = os.environ.get("TESTBRIDGE_LLM_TIMEOUT") or "30"
    timeout_state = "set" if os.environ.get("TESTBRIDGE_LLM_TIMEOUT") else "default"
    print(f"{'llm.timeout':16} {timeout_state:8} {timeout}s")

    mailto = os.environ.get("TESTBRIDGE_OPENALEX_MAILTO")
    print(f"{'openalex.mailto':16} {'set' if mailto else 'unset'}")
    for name, default in (
        ("TESTBRIDGE_OPENALEX_BASE_URL", "https://api.openalex.org"),
        ("TESTBRIDGE_OPENALEX_TIMEOUT", "10"),
    ):
        value = os.environ.get(name)
        state = "set" if value else "default"
        print(f"{name.lower():16} {state:8} {value or default}")

    if missing:
        print("missing: " + ", ".join(missing), file=sys.stderr)
        return 2
    if not args.probe:
        return 0

    config = load_config()
    if config is None:
        print("ERROR doctor: missing environment variables", file=sys.stderr)
        return 2
    client = build_tutor_client(config)
    started = time.perf_counter()
    try:
        reply = client.complete("你是连通性测试，请只回复 ok。", "ok")
    except TutorTimeoutError:
        print("ERROR doctor: upstream timed out", file=sys.stderr)
        return 2
    except TutorUpstreamError as exc:
        print(f"ERROR doctor: {exc}", file=sys.stderr)
        return 2
    elapsed = (time.perf_counter() - started) * 1000
    print(f"latency: {elapsed:.0f} ms")
    print(f"reply: {reply.strip()[:40]}")
    return 0
```

Dispatch:

```python
if args.command == "doctor":
    return _cmd_doctor(args)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_env_commands.py -v`
Expected: PASS（14 passed）

- [x] **Step 5: Commit**

```bash
git add src/testbridge/cli.py tests/test_env_commands.py
git commit -m "feat: add tb doctor"
```

---

### Task 4: README 与验收

**Files:**
- Modify: `README.md`

- [x] **Step 1: Add the Windows one-time setup section**

在 README 的“AI 追问（可选）”前插入：

```markdown
## 一次性配置模型（Windows）

不需要每个终端重复 `export`。首次运行：

```bash
.venv/Scripts/python -m testbridge.cli env init
```

按提示填写 base URL、model、timeout（内容生成建议 90 秒）和 API key；
key 输入不回显、不写入仓库。确认后写入 Windows 用户环境变量。
**重开终端；已运行的 Web 服务需要重启。**

检查当前终端读到的配置（不会显示 key）：

```bash
.venv/Scripts/python -m testbridge.cli doctor
```

需要联网自检时加 `--probe`；默认离线。
```

- [x] **Step 2: Run full tests**

Run: `.venv/Scripts/python -m pytest -q`
Expected: `756 passed`（742 + 新增 14），`3 deselected`

- [x] **Step 3: Manual acceptance**

```bash
.venv/Scripts/python -m testbridge.cli doctor --dry-run  # 若未实现 --dry-run，用 env init --dry-run
.venv/Scripts/python -m testbridge.cli env init --dry-run
```

确认输出中没有 API key；新开终端后 `doctor` 显示配置齐全。

- [x] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document one-time Windows model setup"
```

---

## Self-Review

- **Spec coverage:** 用户环境写入、`env init`、`doctor`、`--probe`、README、密钥不回显、默认离线测试均有任务覆盖。
- **不覆盖：** `.env`、keyring、自动重启服务，符合 spec 非目标。
- **类型一致性：** `write_user_env(values, *, writer)`、`display_url`、`secret_status` 在任务 1 定义，任务 2/3 使用同一签名。
- **已知取舍：** POSIX 只打印 export 行，不改 shell 配置；与 spec 一致。
