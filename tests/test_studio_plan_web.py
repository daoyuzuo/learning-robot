import json
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated",
    category=UserWarning,
)

import pytest
from fastapi.testclient import TestClient

from testbridge.studio.store import DraftStore
from testbridge.tutor.config import TutorConfig
from web.app import create_app

CONFIG = TutorConfig(
    base_url="https://api.example.com/v1", api_key="sk-test",
    model="chat", timeout=5.0,
)
SAMPLE = Path(__file__).parents[1] / "content-packs" / "ros2-qos"


class FakeLlm:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, system: str, user: str) -> str:
        self.prompts.append(user)
        if "课程设计师" in system:
            return json.dumps({
                "pack_title": "计划课", "concepts": [{
                    "id": "c-one", "title": "概念", "domain": "d",
                    "target_level": "L2",
                }],
                "modules": [{
                    "id": "M01", "title": "M", "concepts": ["c-one"],
                    "lessons": [{
                        "id": "L-1", "title": "课", "minutes": 30,
                        "concepts": ["c-one"], "objectives": ["o"],
                        "exercise_intents": ["i"], "research_queries": ["q"],
                    }],
                }],
            })
        return "{}"


def make_app(tmp_path: Path) -> TestClient:
    return TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts",
        studio_packs=tmp_path / "packs",
        studio_llm=FakeLlm(),
        studio_search=type("S", (), {
            "search": lambda self, q, count=10: [],
            "fetch": lambda self, url: "",
        })(),
        studio_config=CONFIG,
        studio_url_checker=lambda urls: {},
    ))


def test_create_with_auto_plan_computes_counts(tmp_path: Path) -> None:
    app = make_app(tmp_path)

    response = app.post("/studio", data={
        "draft_id": "auto", "topic": "ROS2", "level": "L2",
        "searches_per_lesson": "5", "search_backend": "auto",
        "auto_plan": "on", "weekly_hours": "2", "horizon_weeks": "2",
        "purpose": "systematic", "must_cover": "时间同步, 测试",
    }, follow_redirects=False)

    assert response.status_code == 303
    draft = app.app.state.studio_store.load("auto")
    assert draft["plan"]["computed"]["total_lessons"] == 5
    assert draft["module_count"] == 1
    assert draft["lessons_per_module"] == 5
    assert draft["lesson_count"] == 5
    assert draft["plan"]["inputs"]["must_cover"] == ["时间同步", "测试"]


def test_create_with_invalid_auto_plan_is_rejected(tmp_path: Path) -> None:
    app = make_app(tmp_path)

    response = app.post("/studio", data={
        "draft_id": "bad", "topic": "ROS2", "level": "L2",
        "searches_per_lesson": "5", "search_backend": "auto",
        "auto_plan": "on", "weekly_hours": "0", "horizon_weeks": "2",
    }, follow_redirects=False)

    assert response.status_code == 400
    assert app.app.state.studio_store.exists("bad") is False


PLAN_BODY = {
    "inputs": {"weekly_hours": 4, "horizon_weeks": 6,
               "purpose": "interview", "must_cover": ["时间同步"]},
    "computed": {"module_count": 2, "lessons_per_module": 2,
                 "lesson_minutes": 35},
    "guidance": ["多讲测试实操"],
    "confirm": False,
}


def manual_draft(app: TestClient, draft_id: str = "demo") -> None:
    app.post("/studio", data={
        "draft_id": draft_id, "topic": "t", "level": "L3",
        "module_count": "1", "lessons_per_module": "3",
        "searches_per_lesson": "5", "search_backend": "auto",
    })


def test_plan_save_updates_numbers_and_unconfirms(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    manual_draft(app)

    response = app.post("/studio/demo/plan", json=PLAN_BODY)

    assert response.status_code == 200
    draft = app.app.state.studio_store.load("demo")
    assert draft["plan"]["confirmed"] is False
    assert draft["plan"]["computed"]["lessons_per_module"] == 2
    assert draft["plan"]["computed"]["total_lessons"] == 4
    assert draft["plan"]["inputs"]["must_cover"] == ["时间同步"]
    assert draft["module_count"] == 1


def test_plan_confirm_syncs_counts(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    manual_draft(app)

    response = app.post(
        "/studio/demo/plan", json={**PLAN_BODY, "confirm": True}
    )

    assert response.status_code == 200
    draft = app.app.state.studio_store.load("demo")
    assert draft["plan"]["confirmed"] is True
    assert draft["module_count"] == 2
    assert draft["lessons_per_module"] == 2
    assert draft["lesson_count"] == 4


def test_plan_rejects_invalid_numbers(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    # A rejected save keeps the existing plan untouched, so start from one.
    app.post("/studio", data={
        "draft_id": "demo", "topic": "t", "level": "L2",
        "searches_per_lesson": "5", "search_backend": "auto",
        "auto_plan": "on", "weekly_hours": "2", "horizon_weeks": "2",
    })
    before = app.app.state.studio_store.load("demo")["plan"]["computed"]
    bad = {**PLAN_BODY, "computed": {**PLAN_BODY["computed"],
                                     "module_count": 4}}

    response = app.post("/studio/demo/plan", json=bad)

    assert response.status_code == 400
    plan = app.app.state.studio_store.load("demo")["plan"]
    assert plan["confirmed"] is False
    assert plan["computed"] == before


def test_unconfirmed_plan_blocks_outline(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    manual_draft(app)
    app.post("/studio/demo/plan", json=PLAN_BODY)

    response = app.post("/api/studio/demo/outline")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "plan_unconfirmed"


def test_confirmed_plan_allows_outline(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    manual_draft(app)
    app.post("/studio/demo/plan", json={**PLAN_BODY, "confirm": True})

    response = app.post("/api/studio/demo/outline")

    assert response.status_code == 200


def test_draft_page_shows_plan_card(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    manual_draft(app)
    app.post("/studio/demo/plan", json=PLAN_BODY)

    page = app.get("/studio/demo").text

    assert 'data-step="plan"' in page
    assert "多讲测试实操" in page
    assert 'data-action="plan-confirm"' in page
    assert 'data-action="plan-chat"' in page


def test_draft_page_without_plan_shows_manual_mode(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    manual_draft(app)

    page = app.get("/studio/demo").text

    assert 'data-step="plan"' in page
    assert "手动模式</span>" in page
    assert "未确认" not in page
    assert 'data-action="plan-confirm"' not in page


def test_create_with_non_numeric_plan_input_is_rejected(tmp_path: Path) -> None:
    app = make_app(tmp_path)

    response = app.post("/studio", data={
        "draft_id": "nan", "topic": "t", "level": "L2",
        "searches_per_lesson": "5", "search_backend": "auto",
        "auto_plan": "on", "weekly_hours": "abc", "horizon_weeks": "2",
    }, follow_redirects=False)

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "plan_invalid"
    assert app.app.state.studio_store.exists("nan") is False


def test_plan_confirm_requires_a_real_boolean(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    manual_draft(app)

    response = app.post(
        "/studio/demo/plan", json={**PLAN_BODY, "confirm": "false"}
    )

    assert response.status_code == 200
    draft = app.app.state.studio_store.load("demo")
    assert draft["plan"]["confirmed"] is False
    assert draft["module_count"] == 1


@pytest.mark.parametrize("value", [2.0, "2", True])
def test_plan_rejects_non_integer_computed(
    tmp_path: Path, value: object
) -> None:
    app = make_app(tmp_path)
    manual_draft(app)
    bad = {**PLAN_BODY, "computed": {**PLAN_BODY["computed"],
                                     "module_count": value}}

    response = app.post("/studio/demo/plan", json=bad)

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "plan_invalid"


def test_plan_rejects_non_text_guidance(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    manual_draft(app)

    response = app.post(
        "/studio/demo/plan", json={**PLAN_BODY, "guidance": [{"text": "x"}]}
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "plan_invalid"


def test_plan_save_unknown_draft_is_404(tmp_path: Path) -> None:
    app = make_app(tmp_path)

    response = app.post("/studio/nope/plan", json=PLAN_BODY)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "draft_not_found"


def test_plan_save_keeps_existing_messages(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    manual_draft(app)
    app.post("/studio/demo/plan", json=PLAN_BODY)
    store = app.app.state.studio_store
    messages = [{"role": "user", "content": "少讲论文", "at": "2026-10-27"}]

    def seed(draft: dict) -> None:
        draft["plan"]["messages"] = messages

    store.update("demo", seed)

    app.post("/studio/demo/plan", json={**PLAN_BODY, "confirm": True})

    assert store.load("demo")["plan"]["messages"] == messages


def test_plan_save_keeps_a_concurrent_step_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write that lands before the update must survive the plan save.

    The competing writer runs inside a monkeypatched ``DraftStore.update``
    wrapper, so the test is deterministic and needs no threads.
    """
    app = make_app(tmp_path)
    manual_draft(app)
    store = app.app.state.studio_store
    original_update = DraftStore.update

    def competing_update(self, draft_id, mutator):
        self.set_step(draft_id, "outline", status="done")
        return original_update(self, draft_id, mutator)

    monkeypatch.setattr(DraftStore, "update", competing_update)

    response = app.post("/studio/demo/plan", json=PLAN_BODY)

    assert response.status_code == 200
    draft = store.load("demo")
    assert draft["steps"]["outline"]["status"] == "done"
    assert draft["plan"]["computed"]["total_lessons"] == 4


def test_plan_data_block_is_embedded_and_escaped(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    manual_draft(app)
    app.post("/studio/demo/plan", json={
        **PLAN_BODY,
        "guidance": ["多讲 </script><script>alert(1)</script>"],
    })

    page = app.get("/studio/demo").text

    assert 'id="tb-plan-data"' in page
    assert "\u003c/script\u003e" in page
    assert "</script><script>alert(1)" not in page


class PlanLlm(FakeLlm):
    def __init__(self, reply: str) -> None:
        super().__init__()
        self.reply = reply

    def complete(self, system: str, user: str) -> str:
        self.prompts.append(user)
        if "课时计划" in system:
            return self.reply
        return super().complete(system, user)


SUGGESTION = {
    "plan": {"module_count": 1, "lessons_per_module": 3, "lesson_minutes": 35},
    "guidance": ["多讲测试实操"],
    "rationale": "减少理论课",
    "changes": ["total_lessons: 4 -> 3"],
}


def plan_client(tmp_path: Path, llm=None) -> TestClient:
    app = TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts", studio_packs=tmp_path / "packs",
        studio_llm=llm if llm is not None else PlanLlm(json.dumps(SUGGESTION)),
        studio_search=type("S", (), {
            "search": lambda self, q, count=10: [],
            "fetch": lambda self, url: "",
        })(),
        studio_config=CONFIG,
        studio_url_checker=lambda urls: {},
    ))
    manual_draft(app)
    # Start from empty guidance so "chat does not write guidance" is visible.
    app.post("/studio/demo/plan", json={**PLAN_BODY, "guidance": []})
    return app


def test_plan_chat_returns_suggestion_and_logs(tmp_path: Path) -> None:
    app = plan_client(tmp_path)

    response = app.post(
        "/studio/demo/plan/chat", json={"message": "少讲论文，多讲测试实操"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["lessons_per_module"] == 3
    assert body["changes"] == ["total_lessons: 4 -> 3"]
    draft = app.app.state.studio_store.load("demo")
    assert draft["plan"]["messages"][-2]["role"] == "user"
    assert draft["plan"]["messages"][-1]["role"] == "assistant"
    # Chat only suggests; numbers and guidance change when the user applies.
    assert draft["plan"]["computed"]["lessons_per_module"] == 2
    assert draft["plan"]["guidance"] == []
    assert draft["plan"]["confirmed"] is False


def test_plan_chat_keeps_only_the_last_twenty_messages(tmp_path: Path) -> None:
    app = plan_client(tmp_path)
    store = app.app.state.studio_store

    def seed(draft: dict) -> None:
        draft["plan"]["messages"] = [
            {"role": "user", "content": "旧消息", "at": "2026-10-27"}
        ] * 20

    store.update("demo", seed)

    app.post("/studio/demo/plan/chat", json={"message": "调整"})

    messages = store.load("demo")["plan"]["messages"]
    assert len(messages) == 20
    assert messages[-1]["role"] == "assistant"


def test_plan_chat_rejects_bad_model_output(tmp_path: Path) -> None:
    app = plan_client(tmp_path, PlanLlm("not json"))

    response = app.post("/studio/demo/plan/chat", json={"message": "调整"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "plan_invalid"
    draft = app.app.state.studio_store.load("demo")
    assert draft["plan"]["computed"]["lessons_per_module"] == 2
    assert draft["plan"]["guidance"] == []


def test_plan_chat_without_llm_is_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (
        "TESTBRIDGE_LLM_BASE_URL", "TESTBRIDGE_LLM_API_KEY", "TESTBRIDGE_LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    app = TestClient(create_app(
        SAMPLE, tmp_path / "e.db",
        studio_drafts=tmp_path / "drafts", studio_packs=tmp_path / "packs",
        studio_llm=None, studio_search=None, studio_config=None,
    ))
    response = app.post("/studio/demo/plan/chat", json={"message": "x"})
    assert response.status_code == 503


def test_plan_chat_rejects_empty_and_long_messages(tmp_path: Path) -> None:
    app = plan_client(tmp_path)

    for message in ["", "   ", "x" * 501]:
        response = app.post(
            "/studio/demo/plan/chat", json={"message": message}
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "plan_invalid"


def test_plan_chat_without_plan_is_409(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    manual_draft(app)

    response = app.post("/studio/demo/plan/chat", json={"message": "调整"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "plan_missing"


class NestedChatLlm(PlanLlm):
    def __init__(self, holder: dict) -> None:
        super().__init__("{}")
        self.holder = holder
        self.inner_status = None

    def complete(self, system: str, user: str) -> str:
        if "课时计划" in system:
            self.prompts.append(user)
            self.inner_status = self.holder["client"].post(
                "/studio/demo/plan/chat", json={"message": "再来一次"}
            ).status_code
            return json.dumps(SUGGESTION)
        return super().complete(system, user)


def test_plan_chat_second_request_is_409(tmp_path: Path) -> None:
    holder: dict = {}
    llm = NestedChatLlm(holder)
    app = plan_client(tmp_path, llm)
    holder["client"] = app

    response = app.post("/studio/demo/plan/chat", json={"message": "调整"})

    assert response.status_code == 200
    assert llm.inner_status == 409


def test_plan_chat_rejects_non_string_message(tmp_path: Path) -> None:
    app = plan_client(tmp_path)

    response = app.post("/studio/demo/plan/chat", json={"message": {"text": "x"}})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "plan_invalid"


def test_plan_chat_counts_the_llm_call(tmp_path: Path) -> None:
    app = plan_client(tmp_path)
    store = app.app.state.studio_store
    before = store.load("demo")["usage"]["llm_calls"]

    response = app.post("/studio/demo/plan/chat", json={"message": "调整"})

    assert response.status_code == 200
    assert response.json()["usage"] == {"llm_calls": 1}
    assert store.load("demo")["usage"]["llm_calls"] == before + 1


def test_plan_chat_does_not_count_rejected_output(tmp_path: Path) -> None:
    app = plan_client(tmp_path, PlanLlm("not json"))
    store = app.app.state.studio_store
    before = store.load("demo")["usage"]["llm_calls"]

    response = app.post("/studio/demo/plan/chat", json={"message": "调整"})

    assert response.status_code == 422
    assert store.load("demo")["usage"]["llm_calls"] == before
