"""Load and validate interview question banks (tb-interview/1)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, model_validator

from testbridge.contract.models import Id, Level, Rubric, StrictModel

BANK_SCHEMA = "tb-interview/1"


class InterviewBankError(Exception):
    """The bank file is missing, unreadable, or invalid."""


class InterviewQuestion(StrictModel):
    id: Id
    title: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=2000)
    concepts: list[Id] = Field(min_length=1, max_length=3)
    level: Level
    minutes: int = Field(default=8, ge=1, le=30)
    reference_points: list[str] = Field(default_factory=list)
    rubric: Rubric
    follow_ups: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_dimensions(self) -> InterviewQuestion:
        if not self.rubric:
            raise ValueError("rubric must not be empty")
        names = [item.dimension for item in self.rubric]
        if len(names) != len(set(names)):
            raise ValueError("rubric dimensions must be unique")
        return self


class InterviewBank(StrictModel):
    schema_version: Literal["tb-interview/1"] = Field(alias="schema")
    pack: Id
    questions: list[InterviewQuestion] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self) -> InterviewBank:
        ids = [item.id for item in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("question ids must be unique")
        return self

    def by_id(self, question_id: str) -> InterviewQuestion:
        for question in self.questions:
            if question.id == question_id:
                return question
        raise KeyError(question_id)

    def concepts_with_questions(self) -> list[str]:
        return sorted({cid for question in self.questions for cid in question.concepts})


def resolve_bank_path(pack_root: Path, pack_id: str, banks_root: Path) -> Path | None:
    in_pack = pack_root / "interviews.yaml"
    if in_pack.is_file():
        return in_pack
    app_level = banks_root / f"{pack_id}.yaml"
    if app_level.is_file():
        return app_level
    return None


def load_bank(path: Path, *, pack_id: str, concept_ids: set[str]) -> InterviewBank:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise InterviewBankError(f"无法读取题库：{path}") from exc
    except yaml.YAMLError as exc:
        raise InterviewBankError(f"题库 YAML 无效：{exc}") from exc

    try:
        bank = InterviewBank.model_validate(raw)
    except ValidationError as exc:
        raise InterviewBankError(f"题库结构无效：{_first_error(exc)}") from exc

    if bank.pack != pack_id:
        raise InterviewBankError(f"题库 pack 为 {bank.pack}，当前包为 {pack_id}")

    for question in bank.questions:
        unknown = [cid for cid in question.concepts if cid not in concept_ids]
        if unknown:
            raise InterviewBankError(
                f"题目 {question.id} 引用了不存在的概念：{', '.join(unknown)}"
            )
    return bank


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error["loc"])
    return f"{location}: {error['msg']}" if location else error["msg"]
