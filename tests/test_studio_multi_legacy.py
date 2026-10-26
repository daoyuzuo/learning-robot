"""Legacy drafts and flat outlines stay readable after multi-module support."""

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from testbridge.studio.outline import save_outline_html
from testbridge.studio.search import SearchHit
from testbridge.studio.store import DraftStore
from testbridge.tutor.config import TutorConfig
from web.app import create_app

CONFIG = TutorConfig(
    base_url="https://api.example.com/v1", api_key="sk-test",
    model="deepseek-chat", timeout=5.0,
)

CONCEPT = {
    "id": "c-one", "title": "概念一", "domain": "ros2",
    "target_level": "L2", "prerequisites": [], "weight": 1.0,
    "evidence_criteria": [
        {"id": "EV-1", "description": "能解释", "level": "L1"},
    ],
}

LEGACY_OUTLINE = json.dumps({
    "module_title": "旧包",
    "concepts": [CONCEPT],
    "lessons": [
        {"id": "L-1", "title": "课一", "minutes": 20,
         "objectives": ["目标一"], "research_queries": ["query one"]},
        {"id": "L-2", "title": "课二", "minutes": 20,
         "objectives": ["目标二"], "research_queries": ["query two"]},
    ],
}, ensure_ascii=False)

FLAT_OUTLINE = (
    '<article class="tb-outline"><h1 class="tb-module-title">旧包</h1>'
    '<section class="tb-outline-lesson" id="L-1"><h2>课一</h2>'
    '<p class="tb-minutes">20</p><ul class="tb-objectives"><li>目标一</li></ul>'
    '<ul class="tb-queries"><li>query one</li></ul></section></article>'
)


def make_store(tmp_path: Path) -> DraftStore:
    return DraftStore(tmp_path / "drafts")


def create_draft(store: DraftStore, **kwargs) -> dict:
    return store.create(
        draft_id="demo", topic="旧主题", level="L2",
        searches_per_lesson=5, model="m", prompt_version="studio/1",
        **kwargs,
    )


def test_legacy_draft_reads_as_single_module(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    create_draft(store, lesson_count=1)

    draft = store.load("demo")

    assert draft["module_count"] == 1
    assert draft["lessons_per_module"] == 1
    assert draft["lesson_count"] == 1


def test_legacy_flat_outline_save_updates_lessons_keeps_concepts(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    create_draft(store, lesson_count=2)
    store.write("demo", "concepts.yaml", yaml.safe_dump(
        {"schema": "tb/1", "concepts": [CONCEPT]}, allow_unicode=True,
        sort_keys=False,
    ))
    store.write("demo", "modules/M01/module.yaml", yaml.safe_dump(
        {
            "schema": "tb/1", "id": "M01", "title": "旧模块",
            "priority": "P1", "concepts": ["c-one"],
            "lessons": ["L-1"], "order": 1,
        },
        allow_unicode=True, sort_keys=False,
    ))
    store.write("demo", "outline.html", FLAT_OUTLINE)

    saved = FLAT_OUTLINE.replace('id="L-1"', 'id="L-2"')
    modules = save_outline_html(store, "demo", saved)

    assert [module.module_id for module in modules] == ["M01"]
    assert modules[0].concepts is None
    module = yaml.safe_load(store.read("demo", "modules/M01/module.yaml"))
    assert module["concepts"] == ["c-one"]
    assert module["lessons"] == ["L-2"]
    assert module["order"] == 1
    draft = store.load("demo")
    assert "L-2" in draft["steps"]["lessons"]
    assert "L-1" not in draft["steps"]["lessons"]


class RecordingLlm:
    """Flat legacy outline that records the prompt it was given."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, system: str, user: str) -> str:
        self.prompts.append(user)
        return LEGACY_OUTLINE


class NoopSearch:
    def search(self, query: str, count: int = 10) -> list[SearchHit]:
        return []

    def fetch(self, url: str) -> str:
        return ""


SAMPLE = Path(__file__).parents[1] / "content-packs" / "ros2-qos"


def test_old_draft_without_module_fields_runs_outline(tmp_path: Path) -> None:
    llm = RecordingLlm()
    app = TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts",
        studio_packs=tmp_path / "packs",
        studio_llm=llm,
        studio_search=NoopSearch(),
        studio_config=CONFIG,
        studio_inline=True,
        studio_url_checker=lambda urls: {},
    ))
    store = app.app.state.studio_store
    create_draft(store, lesson_count=2)
    draft = store.load("demo")
    draft.pop("module_count", None)
    draft.pop("lessons_per_module", None)
    store.save(draft)

    response = app.post("/api/studio/demo/outline")

    assert response.status_code == 200, response.text
    prompt = llm.prompts[-1]
    assert "模块数：1" in prompt
    assert "每模块课数：2" in prompt
    draft = store.load("demo")
    assert draft["steps"]["outline"]["status"] == "done"
    assert sorted(draft["steps"]["lessons"]) == ["L-1", "L-2"]
    module = yaml.safe_load(store.read("demo", "modules/M01/module.yaml"))
    assert module["lessons"] == ["L-1", "L-2"]
