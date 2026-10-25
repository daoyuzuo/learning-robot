"""Deterministic daily plan: due reviews, new concepts, weak concepts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from testbridge.content.repository import ContentPack
from testbridge.learning.store import Goal, ReviewState
from testbridge.learning.timeutil import iso, parse_iso
from testbridge.mastery.estimator import MasteryView
from testbridge.readiness import LEVEL_ORDER

PlanType = Literal["review", "new", "weak"]

REVIEW_MINUTES = 5
EXERCISE_MINUTES = 10
DEFAULT_LESSON_MINUTES = 20
REASON_PROMPT_LIMIT = 30


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


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _excerpt(text: str, limit: int = REASON_PROMPT_LIMIT) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "…"


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
        self.lesson_index: dict[str, int] = {
            lesson.manifest.id: index for index, lesson in enumerate(self.lessons)
        }
        self.lessons_for_concept: dict[str, list[str]] = {}
        self.lesson_for_exercise: dict[str, str] = {}
        for lesson in self.lessons:
            for concept_id in lesson.manifest.concepts:
                self.lessons_for_concept.setdefault(concept_id, []).append(lesson.manifest.id)
            for exercise_id in lesson.manifest.exercises:
                self.lesson_for_exercise.setdefault(exercise_id, lesson.manifest.id)
        self.exercises_for_concept: dict[str, list[str]] = {}
        for exercise_id in sorted(pack.exercises):
            for concept_id in pack.exercises[exercise_id].concepts:
                self.exercises_for_concept.setdefault(concept_id, []).append(exercise_id)

    def _raw_priority(self, concept_id: str, estimate: float) -> float:
        return self.weights.get(concept_id, 0.0) * (1 - estimate)

    def _priority(self, concept_id: str, estimate: float) -> float:
        return _clamp(self._raw_priority(concept_id, estimate))

    def _order(self, concept_id: str) -> int:
        lessons = self.lessons_for_concept.get(concept_id)
        return self.lesson_index[lessons[0]] if lessons else len(self.lessons)

    def plan(self, now: datetime) -> DailyPlan:
        budget = self.goal.daily_minutes
        fill_limit = max(1, budget)
        now_utc = parse_iso(iso(now))
        items: list[PlanItem] = []
        used_lessons: set[str] = set()
        used_exercises: set[str] = set()
        total = 0

        review_budget = budget * 0.5
        review_minutes = 0
        due_reviews = sorted(
            (review for review in self.due if parse_iso(review.due) <= now_utc),
            key=lambda item: (item.due, item.exercise_id),
        )
        for review in due_reviews:
            if review_minutes + REVIEW_MINUTES > review_budget:
                break
            lesson_id = self.lesson_for_exercise.get(review.exercise_id)
            exercise = self.pack.exercises.get(review.exercise_id)
            label = _excerpt(exercise.prompt) if exercise else review.exercise_id
            items.append(
                PlanItem(
                    type="review",
                    concept_ids=review.concept_ids,
                    lesson_id=lesson_id,
                    exercise_id=review.exercise_id,
                    reason=f"到期复习：{label}",
                    estimated_minutes=REVIEW_MINUTES,
                    priority=1.0,
                )
            )
            review_minutes += REVIEW_MINUTES
            total += REVIEW_MINUTES

        new_candidates: list[tuple[float, int, str]] = []
        for concept_id, view in self.mastery.items():
            concept = self.pack.concepts.get(concept_id)
            if concept is None:
                continue
            lessons = self.lessons_for_concept.get(concept_id)
            if not lessons:
                continue
            if view.exercise_observations + view.other_observations > 0:
                continue
            if any(
                self.mastery.get(prereq) is None
                or self.mastery[prereq].estimate < 0.5
                for prereq in concept.prerequisites
            ):
                continue
            if LEVEL_ORDER.get(view.level, 0) >= LEVEL_ORDER[concept.target_level]:
                continue
            raw = self._raw_priority(concept_id, view.estimate)
            new_candidates.append((raw, self.lesson_index[lessons[0]], concept_id))
        for raw, _, concept_id in sorted(
            new_candidates, key=lambda item: (-item[0], item[1], item[2])
        ):
            lesson_id = next(
                (lid for lid in self.lessons_for_concept[concept_id] if lid not in used_lessons),
                None,
            )
            if lesson_id is None:
                continue
            lesson = self.pack.lessons[lesson_id]
            minutes = lesson.manifest.minutes or DEFAULT_LESSON_MINUTES
            if total + minutes > fill_limit:
                continue
            items.append(PlanItem(
                type="new", concept_ids=[concept_id], lesson_id=lesson_id,
                exercise_id=None, reason=f"先修已满足，下一个概念：{concept_id}",
                estimated_minutes=minutes, priority=_clamp(raw),
            ))
            used_lessons.add(lesson_id)
            total += minutes

        weak_candidates: list[tuple[float, int, str]] = []
        for concept_id, view in self.mastery.items():
            concept = self.pack.concepts.get(concept_id)
            if concept is None:
                continue
            if view.exercise_observations + view.other_observations == 0:
                continue
            if view.estimate >= 0.5:
                continue
            raw = self._raw_priority(concept_id, view.estimate)
            weak_candidates.append((raw, self._order(concept_id), concept_id))
        for raw, _, concept_id in sorted(
            weak_candidates, key=lambda item: (-item[0], item[1], item[2])
        ):
            lesson_id = next(
                (
                    lid
                    for lid in self.lessons_for_concept.get(concept_id, [])
                    if lid not in used_lessons
                ),
                None,
            )
            exercise_id = None
            if lesson_id is None:
                exercise_id = next(
                    (
                        eid
                        for eid in self.exercises_for_concept.get(concept_id, [])
                        if eid not in used_exercises
                    ),
                    None,
                )
                if exercise_id is None:
                    continue
                minutes = EXERCISE_MINUTES
            else:
                minutes = self.pack.lessons[lesson_id].manifest.minutes or DEFAULT_LESSON_MINUTES
            if total + minutes > fill_limit:
                continue
            items.append(PlanItem(
                type="weak", concept_ids=[concept_id], lesson_id=lesson_id,
                exercise_id=exercise_id,
                reason=f"掌握度偏低：{concept_id}（{self.mastery[concept_id].estimate:.2f}）",
                estimated_minutes=minutes, priority=_clamp(raw),
            ))
            if lesson_id is None:
                used_exercises.add(exercise_id)
            else:
                used_lessons.add(lesson_id)
            total += minutes

        empty = not items
        suggestion = None
        if empty:
            below: list[str] = []
            for concept_id, view in self.mastery.items():
                concept = self.pack.concepts.get(concept_id)
                if concept is None:
                    continue
                if LEVEL_ORDER.get(view.level, 0) < LEVEL_ORDER[concept.target_level]:
                    below.append(concept_id)
            if below:
                best = max(below, key=lambda cid: (self.weights.get(cid, 0.0), cid))
                suggestion = f"可选深挖：{best}"
        return DailyPlan(
            items=items, total_minutes=total, budget_minutes=budget,
            empty=empty, suggestion=suggestion,
        )
