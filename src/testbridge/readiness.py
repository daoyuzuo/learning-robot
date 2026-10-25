"""Weighted readiness score with a P0 gate."""

from __future__ import annotations

from dataclasses import dataclass, field

from testbridge.content.repository import ContentPack
from testbridge.learning.store import Goal
from testbridge.learning.weights import concept_weights
from testbridge.mastery.estimator import MasteryView

LEVEL_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}


@dataclass(frozen=True)
class ReadinessView:
    total: float
    by_module: dict[str, float] = field(default_factory=dict)
    gate_active: bool = False
    gate_reasons: list[str] = field(default_factory=list)
    breakdown: list[dict] = field(default_factory=list)


def calculate_readiness(
    pack: ContentPack,
    goal: Goal,
    mastery: dict[str, MasteryView],
) -> ReadinessView:
    weights = concept_weights(pack, goal)
    total_weight = sum(weights.values())
    total = (
        sum(weights[cid] * mastery[cid].estimate for cid in weights) / total_weight
        if total_weight
        else 0.0
    )

    by_module: dict[str, float] = {}
    for module in pack.modules.values():
        module_weight = sum(weights.get(cid, 0.0) for cid in module.concepts)
        by_module[module.id] = (
            sum(weights.get(cid, 0.0) * mastery[cid].estimate for cid in module.concepts)
            / module_weight
            if module_weight
            else 0.0
        )

    gate_reasons: list[str] = []
    for module in pack.modules.values():
        if module.priority != "P0":
            continue
        for concept_id in module.concepts:
            concept = pack.concepts.get(concept_id)
            view = mastery.get(concept_id)
            if concept is None or view is None:
                continue
            if LEVEL_ORDER[view.level] < LEVEL_ORDER[concept.target_level]:
                gate_reasons.append(
                    f"{concept_id} 估计 {view.level}，目标 {concept.target_level}"
                )

    if gate_reasons:
        total = min(total, 0.7)

    breakdown = [
        {
            "concept_id": cid,
            "weight": weights[cid],
            "mastery": mastery[cid].estimate,
            "level": mastery[cid].level,
            "target_level": pack.concepts[cid].target_level,
        }
        for cid in weights
    ]
    return ReadinessView(
        total=total,
        by_module=by_module,
        gate_active=bool(gate_reasons),
        gate_reasons=gate_reasons,
        breakdown=breakdown,
    )
