import pytest
from pydantic import ValidationError

from testbridge.contract.models import (
    Concept,
    ConceptsFile,
    Exercise,
    PackMeta,
    RubricItem,
    ShortAnswer,
)


def test_schema_alias_is_accepted() -> None:
    data = ConceptsFile.model_validate(
        {
            "schema": "tb/1",
            "concepts": [
                {
                    "id": "c-one",
                    "title": "One",
                    "domain": "demo",
                    "target_level": "L2",
                }
            ],
        }
    )
    assert data.concepts[0].id == "c-one"


def test_invalid_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Concept(id="bad id", title="x", domain="demo", target_level="L2")


def test_rubric_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        Exercise(
            id="EX-ONE",
            type="self_assess",
            concepts=["c-one"],
            level="L2",
            prompt="Explain",
            rubric=[RubricItem(dimension="a", weight=0.4, criteria="x")],
        )


def test_single_choice_answer_must_be_an_option() -> None:
    with pytest.raises(ValidationError):
        Exercise(
            id="EX-ONE",
            type="single_choice",
            concepts=["c-one"],
            level="L1",
            prompt="Pick",
            options=[{"id": "a", "text": "A"}],
            answer="b",
        )


def test_self_assess_requires_rubric() -> None:
    with pytest.raises(ValidationError):
        Exercise(
            id="EX-ONE",
            type="self_assess",
            concepts=["c-one"],
            level="L2",
            prompt="Explain",
        )


def test_short_answer_requires_accepted() -> None:
    with pytest.raises(ValidationError):
        ShortAnswer(accepted=[])


def test_pack_version_must_be_semver() -> None:
    with pytest.raises(ValidationError):
        PackMeta(schema="tb/1", id="p", version="1", title="P")
