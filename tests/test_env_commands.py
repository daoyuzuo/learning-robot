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
