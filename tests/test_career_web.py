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

import json

from testbridge.career.store import TargetJdStore
from testbridge.learning.store import LearningStore
from testbridge.tutor.config import TutorConfig

CONFIG = TutorConfig(base_url="http://x", api_key="k", model="fake")

GOOD = json.dumps({
    "target_role": "具身智能测试工程师",
    "requirements": [
        {"text": "精通传感器时间同步", "importance": "must",
         "concepts": ["sensor-time-sync"], "rationale": "核心要求"},
        {"text": "了解时钟漂移", "importance": "high",
         "concepts": ["clock-drift"], "rationale": "加分项"},
        {"text": "熟悉 AUTOSAR", "importance": "high",
         "concepts": [], "rationale": "包内无对应概念"},
    ],
}, ensure_ascii=False)


class FakeClient:
    def __init__(self, reply: str = GOOD) -> None:
        self.reply = reply
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        return self.reply


def parse_form(c: TestClient, jd: str = "招聘时间同步测试工程师") -> dict:
    response = c.post("/target/parse", data={"jd_text": jd})
    assert response.status_code == 200
    return response


def confirm_data(requirements: str = GOOD) -> dict:
    return {
        "source_text": "招聘时间同步测试工程师",
        "target_role": "具身智能测试工程师",
        "requirements_json": json.dumps(
            json.loads(requirements)["requirements"], ensure_ascii=False
        ),
        "model": "fake",
        "weight_sensor-time-sync": "1.6",
        "weight_clock-drift": "1.3",
        "weight_timestamp-basics": "1.0",
    }


def test_parse_renders_review_without_writing(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    response = parse_form(c)
    assert "审核" in response.text
    assert "1.6" in response.text
    assert "熟悉 AUTOSAR" in response.text
    db = tmp_path / "target.db"
    assert TargetJdStore(db).get() is None
    assert LearningStore(db).get_goal().concept_overrides == {}


def test_confirm_writes_goal_and_target(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    parse_form(c)
    response = c.post("/target/confirm", data=confirm_data(),
                      follow_redirects=False)
    assert response.status_code == 303
    db = tmp_path / "target.db"
    goal = LearningStore(db).get_goal()
    assert goal.target_role == "具身智能测试工程师"
    assert goal.concept_overrides == {
        "sensor-time-sync": 1.6, "clock-drift": 1.3,
    }
    target = TargetJdStore(db).get()
    assert target is not None
    assert target.weights == {"sensor-time-sync": 1.6, "clock-drift": 1.3}
    assert target.model == "fake"


def test_confirmed_target_shows_report(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    parse_form(c)
    c.post("/target/confirm", data=confirm_data())
    page = c.get("/target").text
    assert "岗位匹配度" in page
    assert "未达标概念" in page
    assert "sensor-time-sync" in page or "传感器时间同步" in page


def test_manual_mode_without_usable_llm(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient("not json"), config=CONFIG)
    response = parse_form(c)
    assert "自动解析失败" in response.text
    data = {
        "source_text": "招聘时间同步测试工程师",
        "target_role": "测试工程师",
        "requirements_json": "[]",
        "model": "",
        "weight_sensor-time-sync": "1.6",
        "weight_clock-drift": "1.0",
        "weight_timestamp-basics": "1.0",
    }
    assert c.post("/target/confirm", data=data,
                  follow_redirects=False).status_code == 303
    assert LearningStore(tmp_path / "target.db").get_goal().concept_overrides == {
        "sensor-time-sync": 1.6
    }


def test_confirm_rejects_out_of_range_weight(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    parse_form(c)
    data = confirm_data()
    data["weight_clock-drift"] = "3.0"
    assert c.post("/target/confirm", data=data).status_code == 400


def test_confirm_rejects_unknown_concept_in_requirements(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    parse_form(c)
    data = confirm_data()
    data["requirements_json"] = json.dumps([
        {"text": "x", "importance": "must",
         "concepts": ["no-such"], "rationale": ""}
    ], ensure_ascii=False)
    assert c.post("/target/confirm", data=data).status_code == 400


def test_jd_text_is_escaped(tmp_path: Path) -> None:
    c = make_app(tmp_path, llm=FakeClient(), config=CONFIG)
    response = parse_form(c, "<b>JD</b>")
    assert "&lt;b&gt;JD&lt;/b&gt;" in response.text
    assert "<b>JD</b>" not in response.text
