import pytest

from testbridge.interview.bank import InterviewBank
from testbridge.interview.draw import draw_questions

BANK = InterviewBank.model_validate({
    "schema": "tb-interview/1",
    "pack": "p",
    "questions": [
        {"id": f"q-{cid}-1", "title": cid, "prompt": "p",
         "concepts": [cid], "level": "L2", "minutes": 5,
         "rubric": [{"dimension": "d", "weight": 1.0, "criteria": "c"}]}
        for cid in ("c-a", "c-b", "c-c")
    ] + [
        {"id": "q-c-a-2", "title": "a2", "prompt": "p",
         "concepts": ["c-a"], "level": "L2", "minutes": 5,
         "rubric": [{"dimension": "d", "weight": 1.0, "criteria": "c"}]}
    ],
})


def test_weakest_concepts_first() -> None:
    picked = draw_questions(
        BANK,
        concept_weights={"c-a": 1.0, "c-b": 1.0, "c-c": 1.0},
        mastery={"c-a": 0.8, "c-b": 0.2, "c-c": 0.5},
        count=3,
    )
    assert [question.concepts[0] for question in picked] == ["c-b", "c-c", "c-a"]


def test_weight_breaks_mastery_ties() -> None:
    picked = draw_questions(
        BANK,
        concept_weights={"c-a": 0.5, "c-b": 2.0, "c-c": 1.0},
        mastery={"c-a": 0.5, "c-b": 0.5, "c-c": 0.5},
        count=1,
    )
    assert picked[0].concepts == ["c-b"]


def test_override_concepts_come_first() -> None:
    picked = draw_questions(
        BANK,
        concept_weights={"c-a": 1.0, "c-b": 1.0, "c-c": 1.0},
        mastery={"c-a": 0.1, "c-b": 0.9, "c-c": 0.9},
        count=2,
        concept_ids=["c-c"],
    )
    assert picked[0].concepts == ["c-c"]


def test_unknown_override_raises() -> None:
    with pytest.raises(ValueError, match="没有面试题"):
        draw_questions(
            BANK,
            concept_weights={},
            mastery={},
            count=3,
            concept_ids=["nope"],
        )


def test_no_duplicate_questions_and_short_bank() -> None:
    picked = draw_questions(
        BANK,
        concept_weights={"c-a": 1.0, "c-b": 1.0, "c-c": 1.0},
        mastery={},
        count=5,
    )
    assert len(picked) == 4
    assert len({question.id for question in picked}) == 4


def test_same_seed_is_reproducible() -> None:
    first = draw_questions(
        BANK, concept_weights={"c-a": 1.0, "c-b": 1.0, "c-c": 1.0},
        mastery={}, count=2, seed="s1",
    )
    second = draw_questions(
        BANK, concept_weights={"c-a": 1.0, "c-b": 1.0, "c-c": 1.0},
        mastery={}, count=2, seed="s1",
    )
    assert [q.id for q in first] == [q.id for q in second]


def test_count_must_be_positive() -> None:
    with pytest.raises(ValueError):
        draw_questions(BANK, concept_weights={}, mastery={}, count=0)
