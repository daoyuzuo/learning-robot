"""Deterministic daily plan: due reviews, new concepts, weak concepts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from testbridge.content.repository import ContentPack
from testbridge.learning.store import Goal, ReviewState
from testbridge.mastery.estimator import MasteryView

PlanType = Literal["review", "new", "weak"]


@dataclass(frozen=True)
class PlanItem:
    type: PlanType
    concept_ids: list[str]
    lesson_id: str | None
    exercise_id: str | None
    reason: str
    estimated_minutes: int
    priority: float


@dataclass(frozen=True)
class DailyPlan:
    items: list[PlanItem] = field(default_factory=list)
    total_minutes: int = 0
    budget_minutes: int = 45
    empty: bool = True
    suggestion: str | None = None


class Planner:
    def __init__(
        self,
        pack: ContentPack,
        goal: Goal,
        mastery: dict[str, MasteryView],
        due: list[ReviewState],
        weights: dict[str, float],
    ) -> None:
        self.pack = pack
        self.goal = goal
        self.mastery = mastery
        self.due = due
        self.weights = weights
        self.lessons = pack.lessons_in_order()
        self.lessons_for_concept: dict[str, list[str]] = {}
        self.lesson_for_exercise: dict[str, str] = {}
        for lesson in self.lessons:
            for concept_id in lesson.manifest.concepts:
                self.lessons_for_concept.setdefault(concept_id, []).append(lesson.manifest.id)
            for exercise_id in lesson.manifest.exercises:
                self.lesson_for_exercise.setdefault(exercise_id, lesson.manifest.id)

    def plan(self, now: datetime) -> DailyPlan:
        budget = max(1, self.goal.daily_minutes)
        items: list[PlanItem] = []
        used_lessons: set[str] = set()
        total = 0

        review_budget = budget * 0.5
        review_minutes = 0
        for review in sorted(self.due, key=lambda item: (item.due, item.exercise_id)):
            if review_minutes + 5 > review_budget:
                break
            lesson_id = self.lesson_for_exercise.get(review.exercise_id)
            items.append(
                PlanItem(
                    type="review",
                    concept_ids=review.concept_ids,
                    lesson_id=lesson_id,
                    exercise_id=review.exercise_id,
                    reason=f"到期复习：{review.exercise_id}",
                    estimated_minutes=5,
                    priority=1.0,
                )
            )
            review_minutes += 5
            total += 5

        new_candidates = []
        for concept_id, view in self.mastery.items():
            concept = self.pack.concepts[concept_id]
            if view.exercise_observations + view.other_observations > 0:
                continue
            if concept_id not in self.lessons_for_concept:
                continue
            if any(
                self.mastery.get(prereq) is None
                or self.mastery[prereq].estimate < 0.5
                for prereq in concept.prerequisites
            ):
                continue
            new_candidates.append((self.weights.get(concept_id, 0.0) * (1 - view.estimate), concept_id))
        for _, concept_id in sorted(new_candidates, reverse=True):
            lesson_id = next(
                (lid for lid in self.lessons_for_concept[concept_id] if lid not in used_lessons),
                None,
            )
            if lesson_id is None:
                continue
            lesson = self.pack.lessons[lesson_id]
            minutes = lesson.manifest.minutes or 20
            if total + minutes > budget:
                continue
            items.append(PlanItem(
                type="new", concept_ids=[concept_id], lesson_id=lesson_id,
                exercise_id=None, reason=f"先修已满足，下一个概念：{concept_id}",
                estimated_minutes=minutes,
                priority=self.weights.get(concept_id, 0.0) * (1 - self.mastery[concept_id].estimate),
            ))
            used_lessons.add(lesson_id)
            total += minutes

        weak_candidates = []
        for concept_id, view in self.mastery.items():
            if view.exercise_observations + view.other_observations == 0:
                continue
            if view.estimate >= 0.5:
                continue
            if concept_id not in self.lessons_for_concept:
                continue
            weak_candidates.append((self.weights.get(concept_id, 0.0) * (1 - view.estimate), concept_id))
        for _, concept_id in sorted(weak_candidates, reverse=True):
            lesson_id = next(
                (lid for lid in self.lessons_for_concept[concept_id] if lid not in used_lessons),
                None,
            )
            if lesson_id is None:
                continue
            lesson = self.pack.lessons[lesson_id]
            minutes = lesson.manifest.minutes or 20
            if total + minutes > budget:
                continue
            items.append(PlanItem(
                type="weak", concept_ids=[concept_id], lesson_id=lesson_id,
                exercise_id=None, reason=f"掌握度偏低：{concept_id}（{self.mastery[concept_id].estimate:.2f}）",
                estimated_minutes=minutes,
                priority=self.weights.get(concept_id, 0.0) * (1 - self.mastery[concept_id].estimate),
            ))
            used_lessons.add(lesson_id)
            total += minutes

        empty = not items
        suggestion = None
        if empty:
            below = [
                cid for cid, view in self.mastery.items()
                if view.level < self.pack.concepts[cid].target_level
            ]
            if below:
                best = max(below, key=lambda cid: self.weights.get(cid, 0.0))
                suggestion = f"可选深挖：{best}"
        return DailyPlan(
            items=items, total_minutes=total, budget_minutes=budget,
            empty=empty, suggestion=suggestion,
        )
