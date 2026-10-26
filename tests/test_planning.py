import json

import pytest

from testbridge.studio.planning import (
    PlanError,
    PlanInput,
    parse_plan_input,
    parse_plan_suggestion,
    suggest_plan,
    validate_plan,
)


def test_small_plan_uses_lessons_and_minutes() -> None:
    plan = suggest_plan(
        PlanInput(weekly_hours=2, horizon_weeks=2, purpose="systematic", must_cover=[]),
        "L2",
    )
    assert plan.total_lessons == 5
    assert plan.module_count == 1
    assert plan.lessons_per_module == 5
    assert plan.lesson_minutes == 30
    assert plan.total_minutes == 5 * 30


def test_rounds_up_to_minimum_three_lessons() -> None:
    plan = suggest_plan(
        PlanInput(weekly_hours=1, horizon_weeks=1, purpose="systematic", must_cover=[]),
        "L2",
    )
    assert plan.total_lessons == 3
    assert plan.module_count == 1
    assert plan.lessons_per_module == 3


def test_level_and_purpose_adjust_minutes() -> None:
    base = PlanInput(weekly_hours=1, horizon_weeks=1, purpose="systematic", must_cover=[])
    assert suggest_plan(base, "L3").lesson_minutes == 35
    assert suggest_plan(base, "L4").lesson_minutes == 40
    project = PlanInput(weekly_hours=1, horizon_weeks=1, purpose="project", must_cover=[])
    assert suggest_plan(project, "L4").lesson_minutes == 45


def test_large_plan_is_capped_and_says_split() -> None:
    plan = suggest_plan(
        PlanInput(weekly_hours=12, horizon_weeks=8, purpose="interview", must_cover=[]),
        "L3",
    )
    assert plan.total_lessons <= 15
    assert plan.module_count == 3
    assert plan.lessons_per_module == 5
    assert "15" in plan.rationale
    assert "拆" in plan.rationale


def test_total_matches_module_product() -> None:
    for hours, weeks in ((2, 2), (3, 3), (5, 2), (12, 8)):
        plan = suggest_plan(
            PlanInput(hours, weeks, "systematic", []), "L2"
        )
        assert plan.total_lessons == plan.module_count * plan.lessons_per_module


@pytest.mark.parametrize(
    "data",
    [
        {"weekly_hours": 0, "horizon_weeks": 4},
        {"weekly_hours": 81, "horizon_weeks": 4},
        {"weekly_hours": 4, "horizon_weeks": 0},
        {"weekly_hours": 4, "horizon_weeks": 53},
        {"weekly_hours": 4, "horizon_weeks": 4, "purpose": "fun"},
        {"weekly_hours": 4, "horizon_weeks": 4, "must_cover": ["x" * 41]},
        {"weekly_hours": 4, "horizon_weeks": 4, "must_cover": ["x"] * 11},
    ],
)
def test_parse_plan_input_rejects_invalid(data) -> None:
    with pytest.raises(PlanError):
        parse_plan_input(data)


def test_parse_plan_input_defaults_purpose() -> None:
    parsed = parse_plan_input({"weekly_hours": 4, "horizon_weeks": 6})
    assert parsed.purpose == "systematic"
    assert parsed.must_cover == []


def _plan(**overrides) -> dict:
    plan = {
        "inputs": {"weekly_hours": 4, "horizon_weeks": 6, "purpose": "systematic",
                   "must_cover": []},
        "computed": {"module_count": 1, "lessons_per_module": 3,
                     "lesson_minutes": 30, "total_lessons": 3},
        "guidance": ["多讲实操"],
        "confirmed": False,
    }
    plan.update(overrides)
    return plan


def test_validate_plan_accepts_valid() -> None:
    validate_plan(_plan())


@pytest.mark.parametrize(
    "computed",
    [
        {"module_count": 0, "lessons_per_module": 3, "lesson_minutes": 30, "total_lessons": 0},
        {"module_count": 4, "lessons_per_module": 3, "lesson_minutes": 30, "total_lessons": 12},
        {"module_count": 3, "lessons_per_module": 6, "lesson_minutes": 30, "total_lessons": 18},
        {"module_count": 3, "lessons_per_module": 5, "lesson_minutes": 19, "total_lessons": 15},
        {"module_count": 3, "lessons_per_module": 5, "lesson_minutes": 61, "total_lessons": 15},
        {"module_count": 3, "lessons_per_module": 5, "lesson_minutes": 30, "total_lessons": 14},
    ],
)
def test_validate_plan_rejects_bad_computed(computed) -> None:
    with pytest.raises(PlanError):
        validate_plan(_plan(computed=computed))


def test_validate_plan_rejects_too_much_guidance() -> None:
    with pytest.raises(PlanError):
        validate_plan(_plan(guidance=["x"] * 6))
    with pytest.raises(PlanError):
        validate_plan(_plan(guidance=["x" * 81]))


CURRENT = {
    "inputs": {"weekly_hours": 4, "horizon_weeks": 6,
               "purpose": "interview", "must_cover": ["时间同步"]},
    "computed": {"module_count": 2, "lessons_per_module": 3,
                 "lesson_minutes": 35, "total_lessons": 6},
    "guidance": [],
}


def test_parse_plan_suggestion_accepts_valid() -> None:
    raw = json.dumps({
        "plan": {"module_count": 2, "lessons_per_module": 2, "lesson_minutes": 35},
        "guidance": ["多讲测试实操"],
        "rationale": "减少理论课",
        "changes": ["total_lessons: 6 -> 4"],
    })
    result = parse_plan_suggestion(raw, CURRENT)
    assert result["computed"]["lessons_per_module"] == 2
    assert result["guidance"] == ["多讲测试实操"]
    assert result["changes"] == ["total_lessons: 6 -> 4"]


def test_parse_plan_suggestion_rejects_bad_json() -> None:
    with pytest.raises(PlanError):
        parse_plan_suggestion("not json", CURRENT)


def test_parse_plan_suggestion_rejects_out_of_range() -> None:
    raw = json.dumps({"plan": {"module_count": 4, "lessons_per_module": 2,
                              "lesson_minutes": 35}})
    with pytest.raises(PlanError):
        parse_plan_suggestion(raw, CURRENT)


def test_parse_plan_suggestion_rejects_dropping_must_cover() -> None:
    raw = json.dumps({
        "plan": {"module_count": 1, "lessons_per_module": 3, "lesson_minutes": 35},
        "must_cover": [],
    })
    with pytest.raises(PlanError):
        parse_plan_suggestion(raw, CURRENT)


def test_parse_plan_suggestion_keeps_matching_must_cover() -> None:
    raw = json.dumps({
        "plan": {"module_count": 2, "lessons_per_module": 2, "lesson_minutes": 35},
        "must_cover": ["时间同步"],
    })
    assert parse_plan_suggestion(raw, CURRENT)["computed"]["total_lessons"] == 4


def test_parse_plan_suggestion_rejects_bad_guidance_and_changes() -> None:
    ok = {"plan": {"module_count": 2, "lessons_per_module": 2,
                   "lesson_minutes": 35}}
    with pytest.raises(PlanError):
        parse_plan_suggestion(json.dumps({**ok, "guidance": [5]}), CURRENT)
    with pytest.raises(PlanError):
        parse_plan_suggestion(json.dumps({**ok, "changes": [5]}), CURRENT)
    with pytest.raises(PlanError):
        parse_plan_suggestion(json.dumps({**ok, "changes": ["x"] * 11}), CURRENT)


def test_parse_plan_suggestion_strips_code_fence() -> None:
    body = json.dumps({
        "plan": {"module_count": 1, "lessons_per_module": 3, "lesson_minutes": 30},
    })
    raw = "```json\n" + body + "\n```"
    assert parse_plan_suggestion(raw, CURRENT)["computed"]["module_count"] == 1
