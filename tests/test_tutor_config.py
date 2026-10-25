from testbridge.tutor.config import TutorConfig, load_config, missing_vars

FULL = {
    "TESTBRIDGE_LLM_BASE_URL": "https://api.example.com/v1",
    "TESTBRIDGE_LLM_API_KEY": "sk-test",
    "TESTBRIDGE_LLM_MODEL": "demo-model",
}


def test_loads_config_when_all_required_present() -> None:
    config = load_config(FULL)
    assert config == TutorConfig(
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        model="demo-model",
        timeout=30.0,
    )


def test_missing_vars_reports_each_missing_name() -> None:
    assert missing_vars({}) == [
        "TESTBRIDGE_LLM_BASE_URL",
        "TESTBRIDGE_LLM_API_KEY",
        "TESTBRIDGE_LLM_MODEL",
    ]
    assert missing_vars({"TESTBRIDGE_LLM_MODEL": "m"}) == [
        "TESTBRIDGE_LLM_BASE_URL",
        "TESTBRIDGE_LLM_API_KEY",
    ]


def test_disabled_when_any_required_missing() -> None:
    assert load_config({"TESTBRIDGE_LLM_BASE_URL": "https://x/v1"}) is None


def test_custom_timeout_and_invalid_fallback() -> None:
    assert load_config({**FULL, "TESTBRIDGE_LLM_TIMEOUT": "12.5"}).timeout == 12.5
    assert load_config({**FULL, "TESTBRIDGE_LLM_TIMEOUT": "abc"}).timeout == 30.0


def test_api_key_is_not_in_repr() -> None:
    assert "sk-test" not in repr(load_config(FULL))
