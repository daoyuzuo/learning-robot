from pathlib import Path

from testbridge.studio.store import DraftStore
from testbridge.studio.version import PROMPT_VERSION


def test_prompt_version_is_studio_2() -> None:
    assert PROMPT_VERSION == "studio/2"


def test_create_defaults_to_current_prompt_version(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts")
    draft = store.create(
        draft_id="demo", topic="t", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m",
    )
    assert draft["prompt_version"] == PROMPT_VERSION
