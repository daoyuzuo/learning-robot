"""Pick interview questions, weakest concepts first."""

from __future__ import annotations

import random

from testbridge.interview.bank import InterviewBank, InterviewQuestion


def draw_questions(
    bank: InterviewBank,
    *,
    concept_weights: dict[str, float],
    mastery: dict[str, float],
    count: int,
    concept_ids: list[str] | None = None,
    seed: str = "",
) -> list[InterviewQuestion]:
    if count < 1:
        raise ValueError("count must be >= 1")

    by_concept: dict[str, list[InterviewQuestion]] = {}
    for question in bank.questions:
        for concept_id in question.concepts:
            by_concept.setdefault(concept_id, []).append(question)

    def order_key(concept_id: str) -> tuple[float, float, str]:
        """Weakest first; heavier weight breaks ties; concept ID is the last tie-breaker."""
        return (
            mastery.get(concept_id, 0.0),
            -concept_weights.get(concept_id, 1.0),
            concept_id,
        )

    if concept_ids:
        for concept_id in concept_ids:
            if concept_id not in by_concept:
                raise ValueError(f"概念没有面试题：{concept_id}")
        override = list(dict.fromkeys(concept_ids))
        preferred = override + sorted(
            (concept_id for concept_id in by_concept if concept_id not in override),
            key=order_key,
        )
    else:
        preferred = sorted(by_concept, key=order_key)

    rng = random.Random(seed)
    picked: list[InterviewQuestion] = []
    used: set[str] = set()

    for concept_id in preferred:
        if len(picked) >= count:
            break
        options = sorted(
            (q for q in by_concept[concept_id] if q.id not in used),
            key=lambda q: q.id,
        )
        if options:
            question = rng.choice(options)
            picked.append(question)
            used.add(question.id)

    for concept_id in preferred:
        if len(picked) >= count:
            break
        for question in sorted(by_concept[concept_id], key=lambda q: q.id):
            if len(picked) >= count:
                break
            if question.id not in used:
                picked.append(question)
                used.add(question.id)
    return picked
