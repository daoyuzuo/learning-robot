from testbridge.cli import main


def test_tutor_check_reports_missing_config(monkeypatch, capsys) -> None:
    for name in (
        "TESTBRIDGE_LLM_BASE_URL",
        "TESTBRIDGE_LLM_API_KEY",
        "TESTBRIDGE_LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    assert main(["tutor", "check"]) == 2
    assert "TESTBRIDGE_LLM_BASE_URL" in capsys.readouterr().err


def test_tutor_check_prints_model_and_reply(monkeypatch, capsys) -> None:
    monkeypatch.setenv("TESTBRIDGE_LLM_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("TESTBRIDGE_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("TESTBRIDGE_LLM_MODEL", "demo-model")

    class FakeClient:
        def complete(self, system: str, user: str) -> str:
            return "ok"

    monkeypatch.setattr(
        "testbridge.cli.build_tutor_client", lambda config: FakeClient()
    )

    assert main(["tutor", "check"]) == 0
    out = capsys.readouterr().out
    assert "demo-model" in out
    assert "ok" in out
    assert "sk-test" not in out
