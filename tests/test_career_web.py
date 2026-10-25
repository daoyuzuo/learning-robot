import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from web.app import create_app

ROOT = Path(__file__).parents[1]
SAMPLE = ROOT / "content-packs" / "sample-sensors"


def make_app(tmp_path: Path, llm=None, config=None) -> TestClient:
    return TestClient(create_app(
        SAMPLE, tmp_path / "target.db",
        target_llm=llm,
        target_config=config,
    ))


def test_target_empty_state(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    response = c.get("/target")
    assert response.status_code == 200
    assert "还没有目标 JD" in response.text
    assert 'name="jd_text"' in response.text


def test_nav_shows_target(tmp_path: Path) -> None:
    c = make_app(tmp_path)
    assert 'href="/target"' in c.get("/").text
