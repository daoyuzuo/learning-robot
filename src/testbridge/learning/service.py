"""Aggregate evidence, mastery, review scheduling, readiness, and planning."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from testbridge.content.repository import ContentPack
from testbridge.evidence.store import EvidenceEvent, EvidenceStore
from testbridge.learning.store import Goal, LearningStore, MasteryState
from testbridge.learning.timeutil import iso, utcnow
from testbridge.mastery.bkt import BKTState, initial_state, observe
from testbridge.mastery.estimator import HANDOFF_OBSERVATIONS, MasteryView, estimate
from testbridge.mastery.rule import confidence_for, level_for, rule_score
from testbridge.schedule.fsrs import review_event

if TYPE_CHECKING:
    from testbridge.readiness import ReadinessView
    from testbridge.recommend.planner import DailyPlan


class LearningService:
    def __init__(
        self,
        pack: ContentPack,
        evidence: EvidenceStore,
        store: LearningStore,
        learner_id: str = "local",
        now_fn: Callable[[], datetime] = utcnow,
    ) -> None:
        self.pack = pack
        self.evidence = evidence
        self.store = store
        self.learner_id = learner_id
        self.now_fn = now_fn

    def now(self) -> datetime:
        return self.now_fn()

    def goal(self) -> Goal:
        return self.store.get_goal(self.learner_id)

    def mastery(self, concept_id: str) -> MasteryView:
        events = self.evidence.list(concept_id=concept_id, limit=1_000_000)
        state = self.store.get_mastery(self.learner_id, concept_id)
        bkt_state = (
            BKTState(state.bkt_p, state.exercise_observations) if state else None
        )
        return estimate(concept_id, events, self.now(), bkt_state=bkt_state)

    def all_mastery(self) -> dict[str, MasteryView]:
        return {concept_id: self.mastery(concept_id) for concept_id in self.pack.concepts}

    def record(self, event: EvidenceEvent) -> None:
        now = self.now()
        for concept_id in event.concept_ids:
            if concept_id not in self.pack.concepts:
                continue
            existing = self.store.get_mastery(self.learner_id, concept_id)
            bkt = (
                BKTState(existing.bkt_p, existing.exercise_observations)
                if existing
                else initial_state()
            )
            other = existing.other_observations if existing else 0
            if event.kind == "exercise_attempt":
                bkt = observe(bkt, event.outcome == "correct")
            else:
                other += 1
            events = self.evidence.list(concept_id=concept_id, limit=1_000_000)
            rule = rule_score(events, concept_id, now)
            value = bkt.p if bkt.observations >= HANDOFF_OBSERVATIONS else rule.score
            self.store.upsert_mastery(
                MasteryState(
                    learner_id=self.learner_id,
                    concept_id=concept_id,
                    rule_score=rule.score,
                    bkt_p=bkt.p,
                    exercise_observations=bkt.observations,
                    other_observations=other,
                    estimate=value,
                    confidence=confidence_for(bkt.observations, other),
                    level=level_for(value),
                    updated_at=iso(now),
                )
            )
        if event.kind == "exercise_attempt" and event.exercise_id:
            previous = self.store.get_review(self.learner_id, event.exercise_id)
            self.store.upsert_review(
                review_event(
                    event.exercise_id,
                    event.concept_ids,
                    event,
                    previous=previous,
                    learner_id=self.learner_id,
                )
            )

    def due_reviews(self):
        return self.store.due_reviews(self.learner_id, self.now())

    def readiness(self) -> ReadinessView:
        from testbridge.readiness import calculate_readiness

        return calculate_readiness(self.pack, self.goal(), self.all_mastery())

    def today_plan(self) -> DailyPlan:
        from testbridge.learning.weights import concept_weights
        from testbridge.recommend.planner import Planner

        return Planner(
            self.pack,
            self.goal(),
            self.all_mastery(),
            self.due_reviews(),
            concept_weights(self.pack, self.goal()),
        ).plan(self.now())
