"""Assemble derived mastery state from a concept's visible evidence."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from testbridge.evidence.store import EvidenceEvent
from testbridge.learning.store import MasteryState
from testbridge.learning.timeutil import iso
from testbridge.mastery.estimator import HANDOFF_OBSERVATIONS, replay_bkt
from testbridge.mastery.rule import confidence_for, level_for, rule_score


def build_mastery_state(
    *,
    learner_id: str,
    concept_id: str,
    events: Iterable[EvidenceEvent],
    now: datetime,
) -> MasteryState:
    rule = rule_score(events, concept_id, now)
    bkt = replay_bkt(events, concept_id)
    value = bkt.p if bkt.observations >= HANDOFF_OBSERVATIONS else rule.score
    return MasteryState(
        learner_id=learner_id,
        concept_id=concept_id,
        rule_score=rule.score,
        bkt_p=bkt.p,
        exercise_observations=bkt.observations,
        other_observations=rule.other_observations,
        estimate=value,
        confidence=confidence_for(bkt.observations, rule.other_observations),
        level=level_for(value),
        updated_at=iso(now),
    )
