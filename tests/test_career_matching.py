from datetime import datetime, timezone
from pathlib import Path

from testbridge.career.matching import build_report
from testbridge.content.repository import load_pack
from testbridge.learning.store import Goal
from testbridge.mastery.estimator import MasteryView

ROOT = Path(__file__).parents[1]
PACK = load_pack(ROOT / "content-packs" / "sample-sensors")


def view(concept_id: str, estimate: float, level: str) -> MasteryView:
    return MasteryView(
        concept_id=concept_id, rule_score=estimate, bkt_p=estimate,
        estimate=estimate, confidence=1.0, level=level,
        exercise_observations=1, other_observations=0,
    )


def test_report_lists_gaps_for_boosted_concepts() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.2, "L0"),
        "clock-drift": view("clock-drift", 0.9, "L3"),
        "sensor-time-sync": view("sensor-time-sync", 0.4, "L1"),
    }
    goal = Goal(concept_overrides={
        "timestamp-basics": 1.6, "clock-drift": 1.3, "sensor-time-sync": 1.3,
    })
    report = build_report(PACK, goal, mastery)
    assert [row.concept_id for row in report.gaps] == [
        "sensor-time-sync", "timestamp-basics"
    ]
    assert report.gaps[0].level_gap == 2
    assert report.gaps[0].weight == 1.3
    assert report.top == report.gaps[:3]
    assert set(report.weights) == {
        "timestamp-basics", "clock-drift", "sensor-time-sync"
    }


def test_no_overrides_means_no_gaps() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.0, "L0"),
        "clock-drift": view("clock-drift", 0.0, "L0"),
        "sensor-time-sync": view("sensor-time-sync", 0.0, "L0"),
    }
    report = build_report(PACK, Goal(), mastery)
    assert report.gaps == []
    assert report.weights == {}


def test_uncovered_is_passed_through() -> None:
    mastery = {
        concept_id: view(concept_id, 0.0, "L0")
        for concept_id in PACK.concepts
    }
    report = build_report(PACK, Goal(), mastery, uncovered=["熟悉 AUTOSAR"])
    assert report.uncovered == ["熟悉 AUTOSAR"]


def test_report_uses_jd_weighted_readiness() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.0, "L0"),
        "clock-drift": view("clock-drift", 0.0, "L0"),
        "sensor-time-sync": view("sensor-time-sync", 1.0, "L4"),
    }
    base = build_report(PACK, Goal(), mastery)
    boosted = build_report(
        PACK, Goal(concept_overrides={"timestamp-basics": 2.0}), mastery
    )
    assert boosted.readiness.total < base.readiness.total
