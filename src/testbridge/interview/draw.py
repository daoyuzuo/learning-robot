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

    if concept_ids:
        for concept_id in concept_ids:
            if concept_id not in by_concept:
                raise ValueError(f"概念没有面试题：{concept_id}")
        preferred = list(dict.fromkeys(concept_ids))
        preferred += [
            concept_id for concept_id in sorted(by_concept)
            if concept_id not in preferred
        ]
    else:
        preferred = sorted(
            by_concept,
            key=lambda cid: (
                mastery.get(cid, 0.0),
                -concept_weights.get(cid, 1.0),
                cid,
            ),
        )

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
