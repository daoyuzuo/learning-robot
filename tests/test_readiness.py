from pathlib import Path

import pytest

from testbridge.content.repository import load_pack
from testbridge.learning.store import Goal
from testbridge.learning.weights import concept_weights
from testbridge.mastery.estimator import MasteryView
from testbridge.readiness import calculate_readiness

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"
MINIMAL = Path(__file__).parent / "fixtures" / "minimal-pack"
PACK = load_pack(SAMPLE)


def view(concept_id: str, estimate: float, level: str = "L2") -> MasteryView:
    return MasteryView(
        concept_id=concept_id,
        rule_score=estimate,
        bkt_p=estimate,
        estimate=estimate,
        confidence=1.0,
        level=level,
        exercise_observations=3,
        other_observations=0,
    )


def test_weights_use_module_priority_and_override() -> None:
    goal = Goal(learner_id="local", concept_overrides={"sensor-time-sync": 2.0})
    weights = concept_weights(PACK, goal)
    assert weights["sensor-time-sync"] == 2.0  # 1.0 * P0(1.0) * 2.0
    assert weights["timestamp-basics"] == 0.5  # 0.5 * P0(1.0)


def test_readiness_weighted_total() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 1.0, "L1"),
        "clock-drift": view("clock-drift", 0.0, "L2"),
        "sensor-time-sync": view("sensor-time-sync", 1.0, "L3"),
    }
    result = calculate_readiness(PACK, Goal(learner_id="local"), mastery)
    assert 0.0 < result.total <= 1.0
    assert result.gate_active is False
    assert "M01" in result.by_module


def test_readiness_without_p0_is_never_gated() -> None:
    pack = load_pack(MINIMAL)  # M01 is priority P1
    mastery = {"c-one": view("c-one", 0.2, "L0")}  # below target L2
    result = calculate_readiness(pack, Goal(learner_id="local"), mastery)
    assert result.gate_active is False
    assert result.gate_reasons == []
    assert result.total == pytest.approx(0.2)


def test_p0_gate_caps_readiness() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 1.0, "L1"),
        "clock-drift": view("clock-drift", 1.0, "L2"),
        "sensor-time-sync": view("sensor-time-sync", 0.5, "L2"),  # target L3
    }
    result = calculate_readiness(PACK, Goal(learner_id="local"), mastery)
    assert result.gate_active is True
    assert result.total <= 0.7
    assert any("sensor-time-sync" in reason for reason in result.gate_reasons)
