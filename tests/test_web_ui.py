"""O5: shared layout/component classes on the high-traffic pages.

These assertions are intentionally about a few class hooks, not full snapshots:
they fail if a template loses the unified card/badge/table components or the
header regresses to a bare link row.
"""

import warnings
from pathlib import Path

# Environment-level deprecation emitted by the installed FastAPI/Starlette pair.
warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

from fastapi.testclient import TestClient

from web.app import create_app

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"


def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(SAMPLE, tmp_path / "ui.db"))


def test_header_has_skip_link_nav_and_current_page(tmp_path: Path) -> None:
    text = client(tmp_path).get("/today").text
    assert 'class="tb-skip-link"' in text
    assert 'href="#tb-main"' in text
    assert 'id="tb-main"' in text
    assert 'class="tb-nav"' in text
    assert 'href="/today" aria-current="page"' in text
    assert text.count('aria-current="page"') == 1


def test_dashboard_uses_card_and_badge(tmp_path: Path) -> None:
    text = client(tmp_path).get("/").text
    assert 'class="tb-card"' in text
    assert 'class="tb-badge"' in text


def test_today_plan_uses_cards_and_badges(tmp_path: Path) -> None:
    text = client(tmp_path).get("/today").text
    assert 'class="tb-plan"' in text
    assert 'class="tb-card"' in text
    assert 'class="tb-badge"' in text


def test_concepts_uses_table_wrapper_and_badges(tmp_path: Path) -> None:
    text = client(tmp_path).get("/concepts").text
    assert 'class="tb-table-wrap"' in text
    assert 'class="tb-badge"' in text


def test_review_uses_callout_when_empty(tmp_path: Path) -> None:
    text = client(tmp_path).get("/review").text
    assert 'class="tb-callout"' in text


def test_progress_uses_card_and_table_wrapper(tmp_path: Path) -> None:
    text = client(tmp_path).get("/progress").text
    assert 'class="tb-card"' in text
    assert 'class="tb-table-wrap"' in text


def test_lesson_uses_reading_width_and_cards(tmp_path: Path) -> None:
    text = client(tmp_path).get("/lesson/L-SYNC-001").text
    assert 'class="tb-main tb-lesson-main"' in text
    assert 'class="tb-tutor tb-card"' in text
    assert 'class="tb-resources tb-card"' in text
