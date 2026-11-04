"""Label and date-filter behaviour used by every template."""

from __future__ import annotations

from datetime import datetime, timezone

from web.labels import (
    excerpt,
    format_date,
    format_datetime,
    kind_label,
    label,
    level_label,
    outcome_label,
    plan_type_label,
    trust_label,
)


def test_plan_types_are_chinese() -> None:
    assert plan_type_label("review") == "复习"
    assert plan_type_label("new") == "新学"
    assert plan_type_label("weak") == "补弱"


def test_unknown_values_pass_through_untouched() -> None:
    # A new engine enum must never blank a page or raise.
    assert plan_type_label("spaced_repetition") == "spaced_repetition"
    assert outcome_label(None) == ""
    assert label("no_such_kind", "x") == "x"


def test_outcomes_levels_trust_and_kinds() -> None:
    assert outcome_label("correct") == "正确"
    assert outcome_label("partial") == "部分正确"
    assert outcome_label("incorrect") == "错误"
    assert outcome_label("submitted") == "已提交"
    assert level_label("L3") == "L3"
    assert trust_label("A") == "A"
    assert kind_label("interview") == "面试"
    assert kind_label("self_assess") == "自评"
    assert kind_label("artifact") == "产出物"


def test_iso_date_becomes_local_short_form() -> None:
    assert format_date("2020-01-02T00:00:00+00:00") != ""
    assert format_date("2020-01-02T00:00:00+00:00").endswith("日")
    assert format_date("not-a-date") == "not-a-date"
    assert format_date(None) == ""
    assert format_date("") == ""


def test_datetime_renders_local_hour_and_minute() -> None:
    value = "2020-01-02T03:04:00+00:00"
    utc = format_datetime("2020-01-02T03:04:00")
    assert format_datetime(value).endswith(":04")
    # Naive timestamps are treated as already local.
    assert utc == "1月2日 03:04"


def test_date_and_datetime_agree_on_calendar_day_in_utc() -> None:
    moment = datetime(2020, 1, 2, 12, 0, tzinfo=timezone.utc)
    assert format_date(moment.isoformat()).endswith("日")


def test_excerpt_truncates_on_character_boundary() -> None:
    assert excerpt("短题干", 40) == "短题干"
    long_text = "一" * 50
    assert excerpt(long_text, 40) == "一" * 40 + "…"
    assert excerpt(None) == ""
    assert excerpt("  多个   空格  ") == "多个 空格"