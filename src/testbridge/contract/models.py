"""Pydantic models for the tb/1 content contract."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "tb/1"
Level = Literal["L1", "L2", "L3", "L4"]
ExerciseType = Literal["single_choice", "multi_choice", "short_answer", "self_assess", "artifact"]
Trust = Literal["A", "B", "C", "D"]
ResourceKind = Literal[
    "official_docs", "standard", "engineering_blog", "tutorial",
    "repository", "paper", "book", "video", "other",
]
ResourceRole = Literal["required", "supplementary"]
WidgetType = Literal["parameter-svg"]

ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LEVEL_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


def _check_id(value: str) -> str:
    if not ID_PATTERN.fullmatch(value):
        raise ValueError("id must match ^[A-Za-z][A-Za-z0-9-]*$")
    return value


Id = Annotated[str, AfterValidator(_check_id)]


class EvidenceCriterion(StrictModel):
    id: Id
    description: str = Field(min_length=1)
    level: Level


class Concept(StrictModel):
    id: Id
    title: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    target_level: Level
    prerequisites: list[Id] = Field(default_factory=list)
    related: list[Id] = Field(default_factory=list)
    weight: float = Field(default=1.0, gt=0)
    evidence_criteria: list[EvidenceCriterion] = Field(default_factory=list)
    resources: list[Id] = Field(default_factory=list)

    @field_validator("evidence_criteria")
    @classmethod
    def criteria_within_target(
        cls, value: list[EvidenceCriterion], info
    ) -> list[EvidenceCriterion]:
        target = info.data.get("target_level")
        if target:
            for item in value:
                if LEVEL_ORDER[item.level] > LEVEL_ORDER[target]:
                    raise ValueError("evidence criterion level exceeds target_level")
        return value


class ConceptsFile(StrictModel):
    schema_version: Literal["tb/1"] = Field(alias="schema")
    concepts: list[Concept] = Field(min_length=1)


class Option(StrictModel):
    id: Id
    text: str = Field(min_length=1)


class RubricItem(StrictModel):
    dimension: str = Field(min_length=1)
    weight: float = Field(gt=0, le=1)
    criteria: str = Field(min_length=1)


def _check_rubric(value: list[RubricItem]) -> list[RubricItem]:
    if value and abs(sum(item.weight for item in value) - 1.0) > 0.01:
        raise ValueError("rubric weights must sum to 1.0")
    return value


Rubric = Annotated[list[RubricItem], AfterValidator(_check_rubric)]


class Hint(StrictModel):
    level: int = Field(ge=1, le=5)
    text: str = Field(min_length=1)


class ShortAnswer(StrictModel):
    accepted: list[str] = Field(min_length=1)
    min_hits: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def hits_within_accepted(self) -> ShortAnswer:
        if self.min_hits > len(self.accepted):
            raise ValueError("min_hits cannot exceed accepted count")
        return self


class ArtifactSpec(StrictModel):
    accept: list[str] = Field(min_length=1)
    max_size_mb: int = Field(default=10, gt=0)


class Exercise(StrictModel):
    id: Id
    type: ExerciseType
    concepts: list[Id] = Field(min_length=1)
    level: Level
    prompt: str = Field(min_length=1)
    options: list[Option] = Field(default_factory=list)
    answer: str | list[str] | ShortAnswer | None = None
    rubric: Rubric = Field(default_factory=list)
    hints: list[Hint] = Field(default_factory=list)
    difficulty: int = Field(default=1, ge=1, le=5)
    explanation: str = ""
    artifact: ArtifactSpec | None = None

    @field_validator("hints")
    @classmethod
    def unique_hint_levels(cls, value: list[Hint]) -> list[Hint]:
        levels = [item.level for item in value]
        if len(levels) != len(set(levels)):
            raise ValueError("hint levels must be unique")
        return sorted(value, key=lambda item: item.level)

    @model_validator(mode="after")
    def type_specific_fields(self) -> Exercise:
        option_ids = {option.id for option in self.options}
        if self.type in {"single_choice", "multi_choice"}:
            if not self.options:
                raise ValueError(f"{self.type} requires options")
        elif self.options:
            raise ValueError("options are only allowed for choice exercises")

        if self.type == "single_choice":
            if not isinstance(self.answer, str) or self.answer not in option_ids:
                raise ValueError("single_choice answer must be an option id")
        elif self.type == "multi_choice":
            if not isinstance(self.answer, list) or not self.answer:
                raise ValueError("multi_choice answer must be a non-empty list")
            unknown = set(self.answer) - option_ids
            if unknown:
                raise ValueError(f"unknown multi_choice answers: {sorted(unknown)}")
        elif self.type == "short_answer":
            if not isinstance(self.answer, ShortAnswer):
                raise ValueError("short_answer answer must be {accepted, min_hits}")
            if not self.rubric:
                raise ValueError("short_answer requires a rubric")
        elif self.type == "self_assess":
            if not self.rubric:
                raise ValueError("self_assess requires a rubric")
            if self.answer is not None:
                raise ValueError("self_assess must not define answer")
        elif self.type == "artifact":
            if self.artifact is None:
                raise ValueError("artifact exercise requires artifact spec")
            if not self.rubric:
                raise ValueError("artifact exercise requires a rubric")
            if self.answer is not None:
                raise ValueError("artifact exercise must not define answer")

        if self.type != "artifact" and self.artifact is not None:
            raise ValueError("artifact spec is only allowed for artifact exercises")
        return self


class ExercisesFile(StrictModel):
    schema_version: Literal["tb/1"] = Field(alias="schema")
    exercises: list[Exercise] = Field(min_length=1)


class Resource(StrictModel):
    id: Id
    title: str = Field(min_length=1)
    url: str
    type: str = Field(min_length=1)
    kind: ResourceKind = "other"
    role: ResourceRole = "required"
    trust: Trust
    license: str = ""
    last_verified: str = ""
    coverage: list[Id] = Field(default_factory=list)
    why: str = ""

    @field_validator("url")
    @classmethod
    def http_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return value

    @field_validator("last_verified")
    @classmethod
    def date_format(cls, value: str) -> str:
        if value and not DATE_PATTERN.fullmatch(value):
            raise ValueError("last_verified must be YYYY-MM-DD")
        return value


class ResourcesFile(StrictModel):
    schema_version: Literal["tb/1"] = Field(alias="schema")
    resources: list[Resource] = Field(default_factory=list)


class WidgetParameter(StrictModel):
    id: Id
    label: str = Field(min_length=1)
    min: float
    max: float
    default: float

    @model_validator(mode="after")
    def bounds(self) -> WidgetParameter:
        if self.min > self.max:
            raise ValueError("min cannot exceed max")
        if not (self.min <= self.default <= self.max):
            raise ValueError("default must be within [min, max]")
        return self


class ParameterSvgSpec(StrictModel):
    template: str = Field(min_length=1)
    parameters: list[WidgetParameter] = Field(min_length=1)


class Widget(StrictModel):
    id: Id
    type: WidgetType
    title: str = Field(min_length=1)
    spec: ParameterSvgSpec
    caption: str = ""


class WidgetsFile(StrictModel):
    schema_version: Literal["tb/1"] = Field(alias="schema")
    widgets: list[Widget] = Field(default_factory=list)


class PackMeta(StrictModel):
    schema_version: Literal["tb/1"] = Field(alias="schema")
    id: Id
    version: str
    title: str = Field(min_length=1)
    description: str = ""
    language: str = "zh-CN"
    license: str = ""
    authors: list[str] = Field(default_factory=list)
    created: str = ""
    fixture: bool = False

    @field_validator("version")
    @classmethod
    def semver(cls, value: str) -> str:
        if not VERSION_PATTERN.fullmatch(value):
            raise ValueError("version must be MAJOR.MINOR.PATCH")
        return value

    @field_validator("created")
    @classmethod
    def created_date(cls, value: str) -> str:
        if value and not DATE_PATTERN.fullmatch(value):
            raise ValueError("created must be YYYY-MM-DD")
        return value


class Module(StrictModel):
    schema_version: Literal["tb/1"] = Field(alias="schema")
    id: Id
    title: str = Field(min_length=1)
    priority: Literal["P0", "P1", "P2"] = "P1"
    concepts: list[Id] = Field(default_factory=list)
    lessons: list[Id] = Field(default_factory=list)
    order: int = 0


class LessonManifest(StrictModel):
    schema_version: Literal["tb/1"] = Field(alias="schema")
    id: Id
    title: str = Field(min_length=1)
    module: Id
    concepts: list[Id] = Field(min_length=1)
    target_level: Level
    minutes: int = Field(gt=0)
    objectives: list[str] = Field(min_length=1)
    prerequisites: list[Id] = Field(default_factory=list)
    exercises: list[Id] = Field(default_factory=list)
    resources: list[Id] = Field(default_factory=list)
