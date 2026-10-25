import os

import pytest

from testbridge.studio.search import DeepSeekSearch
from testbridge.tutor.client import OpenAICompatibleClient
from testbridge.tutor.config import load_config

pytestmark = pytest.mark.live

requires_live = pytest.mark.skipif(
    os.environ.get("TESTBRIDGE_LIVE") != "1",
    reason="set TESTBRIDGE_LIVE=1 to run live studio tests",
)


@requires_live
def test_search_returns_hits() -> None:
    config = load_config()
    assert config is not None, "missing TESTBRIDGE_LLM_* variables"
    hits = DeepSeekSearch(config).search("ROS 2 executors", count=3)
    assert hits
    assert all(hit.url.startswith("http") for hit in hits)


@requires_live
def test_model_answers() -> None:
    config = load_config()
    assert config is not None
    reply = OpenAICompatibleClient(config).complete("只回复 ok。", "ok")
    assert reply.strip()
