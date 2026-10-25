"""Readiness weights derived from content and goal."""

from __future__ import annotations

from testbridge.content.repository import ContentPack
from testbridge.learning.store import Goal

PRIORITY_MULTIPLIER = {"P0": 1.0, "P1": 0.7, "P2": 0.4}


def concept_weights(pack: ContentPack, goal: Goal) -> dict[str, float]:
    best_priority: dict[str, float] = {}
    for module in pack.modules.values():
        multiplier = PRIORITY_MULTIPLIER.get(module.priority, 0.7)
        for concept_id in module.concepts:
            best_priority[concept_id] = max(
                best_priority.get(concept_id, 0.0), multiplier
            )
    return {
        concept_id: concept.weight
        * best_priority.get(concept_id, 1.0)
        * goal.concept_overrides.get(concept_id, 1.0)
        for concept_id, concept in pack.concepts.items()
    }
