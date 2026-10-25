"""Tutor configuration from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

REQUIRED_VARS = (
    "TESTBRIDGE_LLM_BASE_URL",
    "TESTBRIDGE_LLM_API_KEY",
    "TESTBRIDGE_LLM_MODEL",
)
TIMEOUT_VAR = "TESTBRIDGE_LLM_TIMEOUT"
DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class TutorConfig:
    base_url: str
    api_key: str = field(repr=False)
    model: str
    timeout: float = DEFAULT_TIMEOUT


def missing_vars(env: Mapping[str, str] | None = None) -> list[str]:
    source = os.environ if env is None else env
    return [name for name in REQUIRED_VARS if not source.get(name)]


def load_config(env: Mapping[str, str] | None = None) -> TutorConfig | None:
    source = os.environ if env is None else env
    if missing_vars(source):
        return None
    try:
        timeout = float(source.get(TIMEOUT_VAR) or DEFAULT_TIMEOUT)
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    return TutorConfig(
        base_url=source["TESTBRIDGE_LLM_BASE_URL"],
        api_key=source["TESTBRIDGE_LLM_API_KEY"],
        model=source["TESTBRIDGE_LLM_MODEL"],
        timeout=timeout,
    )
