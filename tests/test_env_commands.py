from testbridge.tutor.env_store import (
    display_url,
    export_lines,
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
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

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
