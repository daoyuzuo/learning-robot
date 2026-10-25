"""Aggregate evidence, mastery, review scheduling, readiness, and planning."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from testbridge.content.repository import ContentPack
from testbridge.evidence.store import EvidenceEvent, EvidenceStore
from testbridge.learning.mastery_builder import build_mastery_state
from testbridge.learning.store import Goal, LearningStore
from testbridge.learning.timeutil import utcnow
from testbridge.mastery.bkt import BKTState
from testbridge.mastery.estimator import MasteryView, estimate
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

    def visible_events(self) -> list[EvidenceEvent]:
        events = self.evidence.list(limit=1_000_000)
        superseded = {e.supersedes for e in events if e.supersedes}
        return [
            e for e in events
            if e.id not in superseded and e.learner_id == self.learner_id
        ]

    def mastery(self, concept_id: str) -> MasteryView:
        return self._mastery(concept_id, self.now())

    def _mastery(self, concept_id: str, now: datetime) -> MasteryView:
        events = [
            e for e in self.visible_events() if concept_id in e.concept_ids
        ]
        state = self.store.get_mastery(self.learner_id, concept_id)
        bkt_state = (
            BKTState(state.bkt_p, state.exercise_observations) if state else None
        )
        return estimate(concept_id, events, now, bkt_state=bkt_state)

    def all_mastery(self) -> dict[str, MasteryView]:
        now = self.now()
        return {
            concept_id: self._mastery(concept_id, now)
            for concept_id in self.pack.concepts
        }

    def record(self, event: EvidenceEvent) -> None:
        now = self.now()
        visible = self.visible_events()
        for concept_id in event.concept_ids:
            if concept_id not in self.pack.concepts:
                continue
            events = [e for e in visible if concept_id in e.concept_ids]
            self.store.upsert_mastery(
                build_mastery_state(
                    learner_id=self.learner_id,
                    concept_id=concept_id,
                    events=events,
                    now=now,
                )
            )
        if event.kind == "exercise_attempt" and event.exercise_id in self.pack.exercises:
            review = None
            for item in sorted(visible, key=lambda e: (e.created_at, e.id)):
                if item.kind != "exercise_attempt" or item.exercise_id != event.exercise_id:
                    continue
                review = review_event(
                    event.exercise_id,
                    item.concept_ids,
                    item,
                    previous=review,
                    learner_id=self.learner_id,
                )
            if review is not None:
                self.store.upsert_review(review)

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
