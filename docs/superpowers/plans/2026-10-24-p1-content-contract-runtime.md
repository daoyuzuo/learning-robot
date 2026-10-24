# P1: Content Contract + Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a content-agnostic teaching engine that validates `tb/1` content packs, renders lessons with exercises, records evidence in SQLite, and exports standalone HTML.

**Architecture:** Pydantic models define the `tb/1` contract; a validator enforces referential integrity and HTML safety; a repository loads validated packs; a renderer mounts exercise forms and widgets into sanitized HTML; FastAPI serves lessons and records evidence; an argparse CLI validates, builds, and serves packs.

**Tech Stack:** Python 3.10+, Pydantic v2, PyYAML, nh3, FastAPI, Jinja2, SQLite (stdlib), pytest, httpx.

**Spec:** `docs/superpowers/specs/2026-10-24-teaching-engine-design.md`

## Global Constraints

- Content schema is exactly `tb/1`; every content file carries `schema: tb/1`.
- Engine modules must never contain domain text or import content-pack files directly.
- Content state and learner state are separate; evidence is append-only.
- Grading is deterministic in P1; no LLM calls in the core path.
- P1 must not implement mastery, FSRS, recommendations, AI generation, interview, or company intel.
- All paths are local; default database is `data/testbridge.db`.
- Python 3.10+; Windows Git Bash commands are used in examples.
- Every task ends with a passing test run and a commit.

---

## Task 0: Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `src/testbridge/__init__.py`
- Create: `src/testbridge/contract/__init__.py`
- Create: `src/testbridge/content/__init__.py`
- Create: `src/testbridge/lesson/__init__.py`
- Create: `src/testbridge/exercise/__init__.py`
- Create: `src/testbridge/evidence/__init__.py`
- Create: `src/testbridge/widgets/__init__.py`
- Create: `web/__init__.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Produces: package `testbridge` with `__version__ = "0.1.0"`.

- [ ] **Step 1: Initialize git and create the environment**

```bash
cd /d/robot
git init
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "testbridge"
version = "0.1.0"
description = "Content-agnostic teaching engine"
requires-python = ">=3.10"
dependencies = [
    "pydantic>=2.7",
    "PyYAML>=6.0",
    "nh3>=0.2.17",
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "jinja2>=3.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",
    "ruff>=0.5",
]

[project.scripts]
tb = "testbridge.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/testbridge"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "."]

[tool.ruff]
line-length = 100
target-version = "py310"
```

- [ ] **Step 3: Create packages and the smoke test**

`src/testbridge/__init__.py`:

```python
"""TestBridge teaching engine."""

__version__ = "0.1.0"
```

Create empty `__init__.py` files in `src/testbridge/contract`, `content`, `lesson`, `exercise`, `evidence`, `widgets`, and `web`.

`tests/test_smoke.py`:

```python
from testbridge import __version__


def test_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 4: Install and run the smoke test**

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src web tests docs README.md CLAUDE.md .gitignore
git commit -m "chore: scaffold testbridge package"
```

---

## Task 1: Contract Models

**Files:**
- Create: `src/testbridge/contract/models.py`
- Test: `tests/test_contract_models.py`

**Interfaces:**
- Produces: `SCHEMA_VERSION`, `Level`, `ExerciseType`, `Trust`, `WidgetType`, `Concept`, `ConceptsFile`, `Exercise`, `ExercisesFile`, `Resource`, `ResourcesFile`, `Widget`, `WidgetsFile`, `PackMeta`, `Module`, `LessonManifest`.

- [ ] **Step 1: Write failing model tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_contract_models.py -q
```

Expected: collection error because `testbridge.contract.models` does not exist.

- [ ] **Step 3: Implement `models.py`**

```python
"""Pydantic models for the tb/1 content contract."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "tb/1"
Level = Literal["L1", "L2", "L3", "L4"]
ExerciseType = Literal["single_choice", "multi_choice", "short_answer", "self_assess", "artifact"]
Trust = Literal["A", "B", "C", "D"]
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
    def hits_within_accepted(self) -> "ShortAnswer":
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
    def type_specific_fields(self) -> "Exercise":
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
    def bounds(self) -> "WidgetParameter":
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
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_contract_models.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/testbridge/contract/models.py tests/test_contract_models.py
git commit -m "feat: add tb/1 contract models"
```

---

## Task 2: Loader, Manifest Extraction, and Fixture Pack

**Files:**
- Create: `src/testbridge/contract/loader.py`
- Create: `tests/fixtures/minimal-pack/pack.yaml`
- Create: `tests/fixtures/minimal-pack/concepts.yaml`
- Create: `tests/fixtures/minimal-pack/exercises.yaml`
- Create: `tests/fixtures/minimal-pack/resources.yaml`
- Create: `tests/fixtures/minimal-pack/widgets.yaml`
- Create: `tests/fixtures/minimal-pack/modules/M01/module.yaml`
- Create: `tests/fixtures/minimal-pack/modules/M01/lessons/L-ONE.html`
- Create: `tests/fixtures/minimal-pack/assets/widgets/demo.svg`
- Test: `tests/test_loader.py`

**Interfaces:**
- Produces: `ContentError`, `load_yaml(path)`, `load_model(path, model)`, `extract_manifest(html)`, `load_lesson_file(path)`.
- `extract_manifest` returns `(LessonManifest, body_html)` with the manifest script removed.

- [ ] **Step 1: Write the fixture pack**

`tests/fixtures/minimal-pack/pack.yaml`:

```yaml
schema: tb/1
id: fixture
version: 0.1.0
title: Fixture Pack
description: Minimal fixture for tests.
language: zh-CN
license: CC-BY-4.0
fixture: true
```

`tests/fixtures/minimal-pack/concepts.yaml`:

```yaml
schema: tb/1
concepts:
  - id: c-one
    title: Concept One
    domain: demo
    target_level: L2
    prerequisites: []
    weight: 1.0
    evidence_criteria:
      - {id: EV-ONE, description: explain one, level: L1}
```

`tests/fixtures/minimal-pack/exercises.yaml`:

```yaml
schema: tb/1
exercises:
  - id: EX-ONE
    type: single_choice
    concepts: [c-one]
    level: L1
    prompt: Pick A.
    options:
      - {id: a, text: A}
      - {id: b, text: B}
    answer: a
    difficulty: 1
```

`tests/fixtures/minimal-pack/resources.yaml`:

```yaml
schema: tb/1
resources:
  - id: DOC-ONE
    title: Example
    url: https://example.com
    type: official-doc
    trust: A
    license: CC-BY-4.0
    last_verified: 2026-10-24
    coverage: [c-one]
    why: demo
```

`tests/fixtures/minimal-pack/widgets.yaml`:

```yaml
schema: tb/1
widgets:
  - id: W-ONE
    type: parameter-svg
    title: Demo
    spec:
      template: assets/widgets/demo.svg
      parameters:
        - {id: offset, label: Offset, min: -10, max: 10, default: 0}
    caption: Demo widget
```

`tests/fixtures/minimal-pack/modules/M01/module.yaml`:

```yaml
schema: tb/1
id: M01
title: Demo Module
concepts: [c-one]
lessons: [L-ONE]
order: 1
```

`tests/fixtures/minimal-pack/modules/M01/lessons/L-ONE.html`:

```html
<script type="application/json" id="tb-manifest">
{
  "schema": "tb/1",
  "id": "L-ONE",
  "title": "Demo Lesson",
  "module": "M01",
  "concepts": ["c-one"],
  "target_level": "L2",
  "minutes": 10,
  "objectives": ["Explain one"],
  "prerequisites": [],
  "exercises": ["EX-ONE"],
  "resources": ["DOC-ONE"]
}
</script>
<article class="tb-lesson">
  <h1>Demo Lesson</h1>
  <p>This is a demo.</p>
  <div data-tb-widget="W-ONE"></div>
  <div data-tb-exercise="EX-ONE"></div>
</article>
```

`tests/fixtures/minimal-pack/assets/widgets/demo.svg`:

```svg
<svg viewBox="0 0 100 40" xmlns="http://www.w3.org/2000/svg">
  <line x1="0" y1="20" x2="100" y2="20" stroke="#ccc"/>
  <circle cx="{{offset}}" cy="20" r="4" fill="#2563eb"/>
</svg>
```

- [ ] **Step 2: Write failing loader tests**

```python
from pathlib import Path

import pytest

from testbridge.contract.loader import (
    ContentError,
    extract_manifest,
    load_lesson_file,
    load_model,
)
from testbridge.contract.models import ConceptsFile

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


def test_load_concepts_file() -> None:
    data = load_model(FIXTURE / "concepts.yaml", ConceptsFile)
    assert data.concepts[0].id == "c-one"


def test_missing_file_raises() -> None:
    with pytest.raises(ContentError):
        load_model(FIXTURE / "missing.yaml", ConceptsFile)


def test_extract_manifest_removes_script() -> None:
    html = (FIXTURE / "modules/M01/lessons/L-ONE.html").read_text(encoding="utf-8")
    manifest, body = extract_manifest(html)
    assert manifest.id == "L-ONE"
    assert "tb-manifest" not in body
    assert "Demo Lesson" in body


def test_missing_manifest_raises() -> None:
    with pytest.raises(ContentError):
        extract_manifest("<article>no manifest</article>")


def test_load_lesson_file() -> None:
    manifest, body = load_lesson_file(FIXTURE / "modules/M01/lessons/L-ONE.html")
    assert manifest.title == "Demo Lesson"
    assert "data-tb-exercise" in body
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/test_loader.py -q
```

Expected: import error for `testbridge.contract.loader`.

- [ ] **Step 4: Implement `loader.py`**

```python
"""Load tb/1 YAML files and extract lesson manifests."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from .models import LessonManifest

T = TypeVar("T", bound=BaseModel)

MANIFEST_RE = re.compile(
    r'<script\b[^>]*\bid=["\']tb-manifest["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


class ContentError(Exception):
    """Raised when a content file cannot be read or validated."""


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise ContentError(f"file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContentError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContentError(f"expected a mapping in {path}")
    return data


def load_model(path: Path, model: type[T]) -> T:
    data = load_yaml(path)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ContentError(f"invalid {model.__name__} in {path}: {exc}") from exc


def extract_manifest(html: str) -> tuple[LessonManifest, str]:
    match = MANIFEST_RE.search(html)
    if not match:
        raise ContentError("missing tb-manifest script")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ContentError(f"invalid tb-manifest JSON: {exc}") from exc
    try:
        manifest = LessonManifest.model_validate(data)
    except ValidationError as exc:
        raise ContentError(f"invalid tb-manifest: {exc}") from exc
    body = html[: match.start()] + html[match.end() :]
    return manifest, body


def load_lesson_file(path: Path) -> tuple[LessonManifest, str]:
    if not path.is_file():
        raise ContentError(f"lesson file not found: {path}")
    return extract_manifest(path.read_text(encoding="utf-8"))
```

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest tests/test_loader.py -q
git add src/testbridge/contract/loader.py tests/test_loader.py tests/fixtures
git commit -m "feat: load tb/1 files and lesson manifests"
```

Expected: all tests pass.

---

## Task 3: HTML Sanitizer

**Files:**
- Create: `src/testbridge/contract/sanitize.py`
- Test: `tests/test_sanitize.py`

**Interfaces:**
- Produces: `sanitize_fragment(html) -> str`, `find_forbidden_html(html) -> list[str]`.

- [ ] **Step 1: Write failing sanitizer tests**

```python
from testbridge.contract.sanitize import find_forbidden_html, sanitize_fragment


def test_strips_script() -> None:
    result = sanitize_fragment('<script>alert(1)</script><p>ok</p>')
    assert "<script" not in result
    assert "<p>ok</p>" in result


def test_strips_event_handlers() -> None:
    result = sanitize_fragment('<p onclick="alert(1)">hi</p>')
    assert "onclick" not in result
    assert ">hi</p>" in result


def test_strips_iframe() -> None:
    result = sanitize_fragment('<iframe src="https://evil.test"></iframe><p>ok</p>')
    assert "<iframe" not in result
    assert "<p>ok</p>" in result


def test_keeps_tb_data_attributes() -> None:
    result = sanitize_fragment('<div data-tb-exercise="EX-ONE"></div>')
    assert 'data-tb-exercise="EX-ONE"' in result


def test_link_gets_rel() -> None:
    result = sanitize_fragment('<a href="https://example.com">x</a>')
    assert 'rel="noopener noreferrer"' in result


def test_find_forbidden_html() -> None:
    issues = find_forbidden_html('<script>x</script><p onclick="x">y</p>')
    assert any("script" in issue for issue in issues)
    assert any("onclick" in issue for issue in issues)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_sanitize.py -q
```

Expected: import error.

- [ ] **Step 3: Implement `sanitize.py`**

```python
"""Allowlist-based HTML sanitization for lesson fragments."""

from __future__ import annotations

import re

import nh3

ALLOWED_TAGS = {
    "article", "section", "header", "footer", "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "ul", "ol", "li", "strong", "em", "code", "pre", "blockquote",
    "figure", "figcaption", "img", "svg", "g", "path", "circle", "rect",
    "line", "polyline", "polygon", "text", "tspan", "defs", "linearGradient",
    "stop", "table", "thead", "tbody", "tr", "th", "td", "a", "span", "div",
    "aside", "details", "summary", "br", "hr",
}

ALLOWED_ATTRIBUTES = {
    "*": {
        "class", "id", "data-tb-block", "data-tb-exercise", "data-tb-widget",
        "data-tb-resource", "data-variant", "data-language", "title",
    },
    "a": {"href", "target", "rel"},
    "img": {"src", "alt", "width", "height"},
    "svg": {"viewBox", "viewbox", "xmlns", "width", "height", "fill", "stroke"},
    "path": {"d", "fill", "stroke", "stroke-width", "transform"},
    "circle": {"cx", "cy", "r", "fill", "stroke", "stroke-width", "transform"},
    "rect": {"x", "y", "width", "height", "rx", "fill", "stroke", "transform"},
    "line": {"x1", "y1", "x2", "y2", "stroke", "stroke-width", "transform"},
    "polyline": {"points", "fill", "stroke", "stroke-width", "transform"},
    "polygon": {"points", "fill", "stroke", "stroke-width", "transform"},
    "text": {"x", "y", "fill", "font-size", "text-anchor"},
    "tspan": {"x", "y", "fill"},
    "stop": {"offset", "stop-color", "stop-opacity"},
}

FORBIDDEN_TAG_RE = re.compile(
    r"<\s*(script|iframe|object|embed|form|input|button|textarea|select)\b",
    re.IGNORECASE,
)
EVENT_ATTR_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
STYLE_ATTR_RE = re.compile(r"\sstyle\s*=", re.IGNORECASE)
JS_URL_RE = re.compile(r"(?:href|src)\s*=\s*[\"']\s*javascript:", re.IGNORECASE)


def sanitize_fragment(html: str) -> str:
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
        strip_comments=True,
    )


def find_forbidden_html(html: str) -> list[str]:
    issues: list[str] = []
    for match in FORBIDDEN_TAG_RE.finditer(html):
        issues.append(f"forbidden tag: {match.group(1).lower()}")
    for match in EVENT_ATTR_RE.finditer(html):
        issues.append(f"forbidden event attribute: {match.group(0).strip()}")
    if STYLE_ATTR_RE.search(html):
        issues.append("forbidden inline style")
    if JS_URL_RE.search(html):
        issues.append("forbidden javascript: URL")
    return issues
```

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest tests/test_sanitize.py -q
git add src/testbridge/contract/sanitize.py tests/test_sanitize.py
git commit -m "feat: add allowlist HTML sanitizer"
```

Expected: all tests pass.

---

## Task 4: Pack Validator

**Files:**
- Create: `src/testbridge/contract/validator.py`
- Test: `tests/test_validator.py`

**Interfaces:**
- Produces: `Issue`, `ValidationReport`, `validate_pack(pack_dir) -> ValidationReport`.
- `ValidationReport.ok` is true when `errors` is empty.

- [ ] **Step 1: Write failing validator tests**

```python
from pathlib import Path

from testbridge.contract.validator import validate_pack

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


def test_fixture_pack_is_valid() -> None:
    report = validate_pack(FIXTURE)
    assert report.ok, report.errors


def test_missing_reference_is_an_error(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "pack.yaml").write_text(
        "schema: tb/1\nid: p\nversion: 0.1.0\ntitle: P\n", encoding="utf-8"
    )
    (pack / "concepts.yaml").write_text(
        "schema: tb/1\nconcepts:\n"
        "  - {id: c-one, title: One, domain: demo, target_level: L2, prerequisites: [missing]}\n",
        encoding="utf-8",
    )
    (pack / "exercises.yaml").write_text("schema: tb/1\nexercises: []\n", encoding="utf-8")
    report = validate_pack(pack)
    assert not report.ok
    assert any("missing" in issue.message for issue in report.errors)


def test_cycle_is_an_error(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "pack.yaml").write_text(
        "schema: tb/1\nid: p\nversion: 0.1.0\ntitle: P\n", encoding="utf-8"
    )
    (pack / "concepts.yaml").write_text(
        "schema: tb/1\nconcepts:\n"
        "  - {id: c-a, title: A, domain: demo, target_level: L2, prerequisites: [c-b]}\n"
        "  - {id: c-b, title: B, domain: demo, target_level: L2, prerequisites: [c-a]}\n",
        encoding="utf-8",
    )
    report = validate_pack(pack)
    assert not report.ok
    assert any(issue.code == "concept.cycle" for issue in report.errors)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_validator.py -q
```

Expected: import error.

- [ ] **Step 3: Implement `validator.py`**

```python
"""Semantic validation for tb/1 content packs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .loader import ContentError, load_lesson_file, load_model
from .models import (
    ConceptsFile,
    ExercisesFile,
    LessonManifest,
    Module,
    PackMeta,
    ResourcesFile,
    WidgetsFile,
)
from .sanitize import find_forbidden_html, sanitize_fragment


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    path: str = ""


@dataclass
class ValidationReport:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _load(path: Path, model, report: ValidationReport):
    try:
        return load_model(path, model)
    except ContentError as exc:
        report.errors.append(Issue("load.invalid", str(exc), str(path)))
        return None


def find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    state: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for nxt in graph.get(node, []):
            if state.get(nxt, 0) == 0:
                visit(nxt)
            elif state.get(nxt) == 1:
                cycles.append(stack[stack.index(nxt) :] + [nxt])
        stack.pop()
        state[node] = 2

    for node in graph:
        if state.get(node, 0) == 0:
            visit(node)
    return cycles


def validate_pack(pack_dir: Path) -> ValidationReport:
    report = ValidationReport()
    if not pack_dir.is_dir():
        report.errors.append(Issue("pack.missing", f"pack directory not found: {pack_dir}"))
        return report

    if _load(pack_dir / "pack.yaml", PackMeta, report) is None:
        return report

    concepts_file = _load(pack_dir / "concepts.yaml", ConceptsFile, report)
    exercises_file = _load(pack_dir / "exercises.yaml", ExercisesFile, report)
    resources_file = _load(pack_dir / "resources.yaml", ResourcesFile, report)
    widgets_path = pack_dir / "widgets.yaml"
    widgets_file = (
        _load(widgets_path, WidgetsFile, report)
        if widgets_path.is_file()
        else WidgetsFile(schema="tb/1", widgets=[])
    )
    if not concepts_file or not exercises_file:
        return report

    concepts = {item.id: item for item in concepts_file.concepts}
    exercises = {item.id: item for item in exercises_file.exercises}
    resources = {item.id: item for item in (resources_file.resources if resources_file else [])}
    widgets = {item.id: item for item in (widgets_file.widgets if widgets_file else [])}

    root = pack_dir.resolve()
    for widget in widgets.values():
        template_path = (pack_dir / widget.spec.template).resolve()
        if root not in template_path.parents:
            report.errors.append(
                Issue("widget.template_path", f"template escapes pack: {widget.spec.template}")
            )
            continue
        if not template_path.is_file():
            report.errors.append(Issue("widget.template", f"missing widget template: {template_path}"))
            continue
        template_text = template_path.read_text(encoding="utf-8")
        for issue in find_forbidden_html(template_text):
            report.errors.append(Issue("widget.template", issue, str(template_path)))

    for label, items in (("concept", concepts), ("exercise", exercises), ("resource", resources)):
        if len(items) != len(
            concepts_file.concepts if label == "concept"
            else exercises_file.exercises if label == "exercise"
            else (resources_file.resources if resources_file else [])
        ):
            report.errors.append(Issue(f"{label}.duplicate", f"duplicate {label} id"))

    modules: dict[str, Module] = {}
    manifests: dict[str, LessonManifest] = {}

    modules_dir = pack_dir / "modules"
    for module_path in sorted(modules_dir.glob("*/module.yaml")):
        module = _load(module_path, Module, report)
        if module is None:
            continue
        if module.id in modules:
            report.errors.append(Issue("module.duplicate", f"duplicate module {module.id}"))
        modules[module.id] = module
        for lesson_id in module.lessons:
            lesson_path = module_path.parent / "lessons" / f"{lesson_id}.html"
            try:
                manifest, body = load_lesson_file(lesson_path)
            except ContentError as exc:
                report.errors.append(Issue("lesson.load", str(exc), str(lesson_path)))
                continue
            if manifest.id != lesson_id:
                report.errors.append(
                    Issue("lesson.id", f"manifest id {manifest.id} != file id {lesson_id}", str(lesson_path))
                )
            if manifest.module != module.id:
                report.errors.append(
                    Issue("lesson.module", f"manifest module {manifest.module} != {module.id}", str(lesson_path))
                )
            if manifest.id in manifests:
                report.errors.append(Issue("lesson.duplicate", f"duplicate lesson {manifest.id}"))
            manifests[manifest.id] = manifest
            try:
                sanitize_fragment(body)
            except Exception as exc:  # nh3 raises ValueError on bad input
                report.errors.append(Issue("lesson.html", f"sanitizer failed: {exc}", str(lesson_path)))
            for issue in find_forbidden_html(body):
                report.errors.append(Issue("lesson.html", issue, str(lesson_path)))
            for exercise_id in re.findall(r'data-tb-exercise="([^"]+)"', body):
                if exercise_id not in exercises:
                    report.errors.append(
                        Issue("lesson.exercise_ref", f"{manifest.id} mounts missing exercise {exercise_id}", str(lesson_path))
                    )
            for widget_id in re.findall(r'data-tb-widget="([^"]+)"', body):
                if widget_id not in widgets:
                    report.errors.append(
                        Issue("lesson.widget_ref", f"{manifest.id} mounts missing widget {widget_id}", str(lesson_path))
                    )

    if not manifests:
        report.errors.append(Issue("pack.no_lessons", "pack has no lessons", str(pack_dir)))

    graph = {cid: list(concept.prerequisites) for cid, concept in concepts.items()}
    for cycle in find_cycles(graph):
        report.errors.append(Issue("concept.cycle", f"prerequisite cycle: {' -> '.join(cycle)}"))

    def require(label: str, refs: list[str], pool: dict, owner: str) -> None:
        for ref in refs:
            if ref not in pool:
                report.errors.append(Issue(f"{label}.missing", f"{owner} references missing {label} {ref}"))

    for concept in concepts.values():
        require("concept", concept.prerequisites, concepts, concept.id)
        require("concept", concept.related, concepts, concept.id)
        require("resource", concept.resources, resources, concept.id)
    for exercise in exercises.values():
        require("concept", exercise.concepts, concepts, exercise.id)
    for resource in resources.values():
        require("concept", resource.coverage, concepts, resource.id)
    for module in modules.values():
        require("concept", module.concepts, concepts, module.id)
        require("lesson", module.lessons, manifests, module.id)
    for manifest in manifests.values():
        require("module", [manifest.module], modules, manifest.id)
        require("concept", manifest.concepts, concepts, manifest.id)
        require("concept", manifest.prerequisites, concepts, manifest.id)
        require("exercise", manifest.exercises, exercises, manifest.id)
        require("resource", manifest.resources, resources, manifest.id)

    lesson_concepts = {cid for manifest in manifests.values() for cid in manifest.concepts}
    exercise_concepts = {cid for exercise in exercises.values() for cid in exercise.concepts}
    for cid, concept in concepts.items():
        if cid not in lesson_concepts:
            report.warnings.append(Issue("concept.no_lesson", f"{cid} has no lesson", str(pack_dir)))
        if cid not in exercise_concepts:
            report.warnings.append(Issue("concept.no_exercise", f"{cid} has no exercise", str(pack_dir)))
    for manifest in manifests.values():
        if not manifest.exercises:
            report.warnings.append(Issue("lesson.no_exercise", f"{manifest.id} has no exercises"))
        if not manifest.resources:
            report.warnings.append(Issue("lesson.no_resource", f"{manifest.id} has no resources"))
    for resource in resources.values():
        if not resource.last_verified:
            report.warnings.append(Issue("resource.no_verified", f"{resource.id} has no last_verified"))
        if not resource.license:
            report.warnings.append(Issue("resource.no_license", f"{resource.id} has no license"))

    return report
```

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest tests/test_validator.py -q
git add src/testbridge/contract/validator.py tests/test_validator.py
git commit -m "feat: validate tb/1 referential integrity and HTML safety"
```

Expected: all tests pass.

---

## Task 5: Content Repository

**Files:**
- Create: `src/testbridge/content/repository.py`
- Test: `tests/test_repository.py`

**Interfaces:**
- Produces: `Lesson`, `ContentPack`, `ContentValidationError`, `load_pack(path)`, `list_packs(root)`, `PackInfo`.
- `ContentPack` exposes `concepts`, `exercises`, `resources`, `widgets`, `modules`, `lessons` dicts, plus `lessons_in_order()` and `prev_next(lesson_id)`.

- [ ] **Step 1: Write failing repository tests**

```python
from pathlib import Path

import pytest

from testbridge.content.repository import (
    ContentValidationError,
    load_pack,
)

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


def test_load_pack() -> None:
    pack = load_pack(FIXTURE)
    assert pack.meta.id == "fixture"
    assert pack.concept("c-one").title == "Concept One"
    assert pack.exercise("EX-ONE").type == "single_choice"
    assert pack.lesson("L-ONE").manifest.module == "M01"


def test_lessons_in_order_and_pager() -> None:
    pack = load_pack(FIXTURE)
    lessons = pack.lessons_in_order()
    assert [item.manifest.id for item in lessons] == ["L-ONE"]
    prev, nxt = pack.prev_next("L-ONE")
    assert prev is None and nxt is None


def test_invalid_pack_raises(tmp_path: Path) -> None:
    pack_dir = tmp_path / "bad"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "schema: tb/1\nid: bad\nversion: 0.1.0\ntitle: Bad\n", encoding="utf-8"
    )
    with pytest.raises(ContentValidationError):
        load_pack(pack_dir)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_repository.py -q
```

Expected: import error.

- [ ] **Step 3: Implement `repository.py`**

```python
"""Load validated content packs and provide read-only queries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from testbridge.contract.loader import ContentError, load_lesson_file, load_model
from testbridge.contract.models import (
    Concept,
    ConceptsFile,
    Exercise,
    ExercisesFile,
    LessonManifest,
    Module,
    PackMeta,
    Resource,
    ResourcesFile,
    Widget,
    WidgetsFile,
)
from testbridge.contract.validator import ValidationReport, validate_pack


class ContentValidationError(Exception):
    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        super().__init__(f"content pack has {len(report.errors)} error(s)")


@dataclass(frozen=True)
class Lesson:
    manifest: LessonManifest
    body_html: str
    path: Path


@dataclass(frozen=True)
class ContentPack:
    root: Path
    meta: PackMeta
    concepts: dict[str, Concept]
    exercises: dict[str, Exercise]
    resources: dict[str, Resource]
    widgets: dict[str, Widget]
    modules: dict[str, Module]
    lessons: dict[str, Lesson]

    def concept(self, concept_id: str) -> Concept:
        return self.concepts[concept_id]

    def lesson(self, lesson_id: str) -> Lesson:
        return self.lessons[lesson_id]

    def exercise(self, exercise_id: str) -> Exercise:
        return self.exercises[exercise_id]

    def resource(self, resource_id: str) -> Resource:
        return self.resources[resource_id]

    def widget(self, widget_id: str) -> Widget:
        return self.widgets[widget_id]

    def lessons_in_order(self) -> list[Lesson]:
        ordered: list[Lesson] = []
        for module in sorted(self.modules.values(), key=lambda item: (item.order, item.id)):
            for lesson_id in module.lessons:
                if lesson_id in self.lessons:
                    ordered.append(self.lessons[lesson_id])
        return ordered

    def prev_next(self, lesson_id: str) -> tuple[Lesson | None, Lesson | None]:
        ordered = self.lessons_in_order()
        for index, lesson in enumerate(ordered):
            if lesson.manifest.id == lesson_id:
                prev_lesson = ordered[index - 1] if index > 0 else None
                next_lesson = ordered[index + 1] if index + 1 < len(ordered) else None
                return prev_lesson, next_lesson
        return None, None


@dataclass(frozen=True)
class PackInfo:
    path: Path
    meta: PackMeta


def load_pack(pack_dir: Path) -> ContentPack:
    report = validate_pack(pack_dir)
    if not report.ok:
        raise ContentValidationError(report)

    meta = load_model(pack_dir / "pack.yaml", PackMeta)
    concepts_file = load_model(pack_dir / "concepts.yaml", ConceptsFile)
    exercises_file = load_model(pack_dir / "exercises.yaml", ExercisesFile)
    resources_path = pack_dir / "resources.yaml"
    widgets_path = pack_dir / "widgets.yaml"
    resources_file = load_model(resources_path, ResourcesFile) if resources_path.is_file() else ResourcesFile(schema="tb/1", resources=[])
    widgets_file = load_model(widgets_path, WidgetsFile) if widgets_path.is_file() else WidgetsFile(schema="tb/1", widgets=[])

    modules: dict[str, Module] = {}
    lessons: dict[str, Lesson] = {}
    for module_path in sorted((pack_dir / "modules").glob("*/module.yaml")):
        module = load_model(module_path, Module)
        modules[module.id] = module
        for lesson_id in module.lessons:
            path = module_path.parent / "lessons" / f"{lesson_id}.html"
            manifest, body = load_lesson_file(path)
            lessons[lesson_id] = Lesson(manifest=manifest, body_html=body, path=path)

    return ContentPack(
        root=pack_dir,
        meta=meta,
        concepts={item.id: item for item in concepts_file.concepts},
        exercises={item.id: item for item in exercises_file.exercises},
        resources={item.id: item for item in resources_file.resources},
        widgets={item.id: item for item in widgets_file.widgets},
        modules=modules,
        lessons=lessons,
    )


def list_packs(root: Path) -> list[PackInfo]:
    infos: list[PackInfo] = []
    for pack_yaml in sorted(root.glob("*/pack.yaml")):
        try:
            meta = load_model(pack_yaml, PackMeta)
        except ContentError:
            continue
        infos.append(PackInfo(path=pack_yaml.parent, meta=meta))
    return infos
```

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest tests/test_repository.py -q
git add src/testbridge/content/repository.py tests/test_repository.py
git commit -m "feat: load validated content packs"
```

Expected: all tests pass.

---

## Task 6: Exercise Grading and Hints

**Files:**
- Create: `src/testbridge/exercise/grading.py`
- Test: `tests/test_grading.py`

**Interfaces:**
- Produces: `GradeResult`, `normalize(text)`, `grade(exercise, response)`, `get_hint(exercise, level)`.
- `GradeResult` fields: `outcome`, `correct`, `score`, `max_score`, `feedback`, `details`.

- [ ] **Step 1: Write failing grading tests**

```python
from testbridge.contract.models import Exercise, Hint, RubricItem, ShortAnswer
from testbridge.exercise.grading import get_hint, grade


def choice() -> Exercise:
    return Exercise(
        id="EX-C", type="single_choice", concepts=["c-one"], level="L1",
        prompt="Pick", options=[{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        answer="a", hints=[Hint(level=1, text="think")],
    )


def test_single_choice() -> None:
    assert grade(choice(), "a").correct is True
    assert grade(choice(), "b").correct is False


def test_multi_choice_partial() -> None:
    ex = Exercise(
        id="EX-M", type="multi_choice", concepts=["c-one"], level="L2",
        prompt="Pick", options=[{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        answer=["a", "b"],
    )
    result = grade(ex, ["a"])
    assert result.outcome == "partial"
    assert result.score == 0.5


def test_short_answer_keywords() -> None:
    ex = Exercise(
        id="EX-S", type="short_answer", concepts=["c-one"], level="L2",
        prompt="Explain", answer=ShortAnswer(accepted=["时间戳", "阈值"], min_hits=1),
        rubric=[RubricItem(dimension="x", weight=1.0, criteria="x")],
    )
    assert grade(ex, "时间戳要对齐").correct is True
    assert grade(ex, "不知道").correct is False


def test_self_assess_scores_checked_dimensions() -> None:
    ex = Exercise(
        id="EX-A", type="self_assess", concepts=["c-one"], level="L2",
        prompt="Rate", rubric=[
            RubricItem(dimension="机制", weight=0.5, criteria="x"),
            RubricItem(dimension="测试", weight=0.5, criteria="y"),
        ],
    )
    result = grade(ex, {"checked": ["机制"]})
    assert result.outcome == "submitted"
    assert result.score == 0.5


def test_artifact_requires_path() -> None:
    ex = Exercise(
        id="EX-F", type="artifact", concepts=["c-one"], level="L3",
        prompt="Upload", artifact={"accept": ["log"], "max_size_mb": 1},
        rubric=[RubricItem(dimension="x", weight=1.0, criteria="x")],
    )
    assert grade(ex, {"path": "a.log"}).outcome == "submitted"
    assert grade(ex, {"notes": "no path"}).outcome == "incorrect"


def test_hint_levels() -> None:
    ex = choice()
    assert get_hint(ex, 1) == "think"
    assert get_hint(ex, 2) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_grading.py -q
```

Expected: import error.

- [ ] **Step 3: Implement `grading.py`**

```python
"""Deterministic grading for P1 exercise types."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from testbridge.contract.models import Exercise, ShortAnswer

Outcome = Literal["correct", "incorrect", "partial", "submitted"]
PUNCTUATION_RE = re.compile(r"[\s,，。.!！?？;；:：、\"'“”‘’()（）\[\]【】]+")


@dataclass(frozen=True)
class GradeResult:
    outcome: Outcome
    correct: bool | None
    score: float | None
    max_score: float | None
    feedback: str
    details: dict[str, Any] = field(default_factory=dict)


def normalize(text: str) -> str:
    return PUNCTUATION_RE.sub("", str(text)).lower()


def grade(exercise: Exercise, response: Any) -> GradeResult:
    if exercise.type == "single_choice":
        selected = response if isinstance(response, str) else None
        ok = selected == exercise.answer
        return GradeResult(
            "correct" if ok else "incorrect", ok, 1.0 if ok else 0.0, 1.0,
            "回答正确。" if ok else "再想想。", {"selected": selected},
        )

    if exercise.type == "multi_choice":
        expected = set(exercise.answer or [])
        selected = set(response or []) if isinstance(response, list) else set()
        hits = len(expected & selected)
        score = hits / len(expected) if expected else 0.0
        ok = selected == expected
        outcome: Outcome = "correct" if ok else ("partial" if hits else "incorrect")
        return GradeResult(
            outcome, ok, score, 1.0,
            "全对。" if ok else f"命中了 {hits}/{len(expected)} 个正确项。",
            {"selected": sorted(selected), "expected": sorted(expected)},
        )

    if exercise.type == "short_answer":
        answer = exercise.answer
        if not isinstance(answer, ShortAnswer):
            raise ValueError("short_answer is missing accepted keywords")
        text = normalize(response)
        matched = [item for item in answer.accepted if normalize(item) in text]
        ok = len(matched) >= answer.min_hits
        score = len(matched) / len(answer.accepted)
        return GradeResult(
            "correct" if ok else "incorrect", ok, score, 1.0,
            "命中关键点。" if ok else "关键点不足，再看一遍材料。",
            {"matched": matched, "missing": [item for item in answer.accepted if item not in matched]},
        )

    if exercise.type == "self_assess":
        checked = set(response.get("checked", [])) if isinstance(response, dict) else set()
        score = sum(item.weight for item in exercise.rubric if item.dimension in checked)
        return GradeResult(
            "submitted", None, score, 1.0, "已记录自评。", {"checked": sorted(checked)},
        )

    if exercise.type == "artifact":
        payload = response if isinstance(response, dict) else {}
        path = str(payload.get("path", "")).strip()
        if not path:
            return GradeResult("incorrect", False, 0.0, 1.0, "请填写附件路径。", payload)
        checked = set(payload.get("checked", []))
        score = sum(item.weight for item in exercise.rubric if item.dimension in checked)
        return GradeResult("submitted", None, score, 1.0, "已记录产出物。", payload)

    raise ValueError(f"unsupported exercise type: {exercise.type}")


def get_hint(exercise: Exercise, level: int) -> str | None:
    for hint in exercise.hints:
        if hint.level == level:
            return hint.text
    return None
```

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest tests/test_grading.py -q
git add src/testbridge/exercise/grading.py tests/test_grading.py
git commit -m "feat: grade exercises deterministically"
```

Expected: all tests pass.

---

## Task 7: SQLite Evidence Store

**Files:**
- Create: `src/testbridge/evidence/store.py`
- Test: `tests/test_evidence_store.py`

**Interfaces:**
- Produces: `EvidenceEvent`, `EvidenceStore`, `new_event(...)`.
- `EvidenceStore` methods: `append`, `list`, `count`, `export_jsonl`, `import_jsonl`.

- [ ] **Step 1: Write failing evidence tests**

```python
from pathlib import Path

from testbridge.evidence.store import EvidenceStore, new_event


def test_append_and_list(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "e.db")
    event = new_event(
        kind="exercise_attempt", lesson_id="L-ONE", exercise_id="EX-ONE",
        concept_ids=["c-one"], outcome="correct", score=1.0, max_score=1.0,
    )
    store.append(event)
    rows = store.list(lesson_id="L-ONE")
    assert len(rows) == 1
    assert rows[0].exercise_id == "EX-ONE"
    assert store.count(lesson_id="L-ONE") == 1


def test_export_import_is_idempotent(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "e.db")
    event = new_event(kind="exercise_attempt", concept_ids=["c-one"], outcome="correct")
    store.append(event)
    export_path = tmp_path / "e.jsonl"
    assert store.export_jsonl(export_path) == 1
    assert store.import_jsonl(export_path) == 0
    assert store.count() == 1


def test_concept_filter(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "e.db")
    store.append(new_event(kind="exercise_attempt", concept_ids=["c-one"], outcome="correct"))
    store.append(new_event(kind="exercise_attempt", concept_ids=["c-two"], outcome="incorrect"))
    assert len(store.list(concept_id="c-one")) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_evidence_store.py -q
```

Expected: import error.

- [ ] **Step 3: Implement `store.py`**

```python
"""Append-only SQLite evidence store."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS evidence (
  id TEXT PRIMARY KEY,
  learner_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  session_id TEXT,
  lesson_id TEXT,
  exercise_id TEXT,
  concept_ids TEXT NOT NULL,
  outcome TEXT,
  score REAL,
  max_score REAL,
  payload TEXT NOT NULL,
  source TEXT NOT NULL,
  created_at TEXT NOT NULL,
  supersedes TEXT
);
CREATE INDEX IF NOT EXISTS idx_evidence_lesson ON evidence(lesson_id);
CREATE INDEX IF NOT EXISTS idx_evidence_created ON evidence(created_at);
"""


@dataclass(frozen=True)
class EvidenceEvent:
    id: str
    learner_id: str
    kind: str
    concept_ids: list[str]
    payload: dict[str, Any]
    source: str
    created_at: str
    session_id: str | None = None
    lesson_id: str | None = None
    exercise_id: str | None = None
    outcome: str | None = None
    score: float | None = None
    max_score: float | None = None
    supersedes: str | None = None


def new_event(
    *,
    kind: str,
    concept_ids: list[str],
    lesson_id: str | None = None,
    exercise_id: str | None = None,
    outcome: str | None = None,
    score: float | None = None,
    max_score: float | None = None,
    payload: dict[str, Any] | None = None,
    source: str = "web",
    session_id: str | None = None,
    learner_id: str = "local",
) -> EvidenceEvent:
    return EvidenceEvent(
        id=uuid4().hex,
        learner_id=learner_id,
        kind=kind,
        concept_ids=concept_ids,
        payload=payload or {},
        source=source,
        created_at=datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
        lesson_id=lesson_id,
        exercise_id=exercise_id,
        outcome=outcome,
        score=score,
        max_score=max_score,
    )


class EvidenceStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA_SQL)

    def append(self, event: EvidenceEvent) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO evidence
                (id, learner_id, kind, session_id, lesson_id, exercise_id,
                 concept_ids, outcome, score, max_score, payload, source,
                 created_at, supersedes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id, event.learner_id, event.kind, event.session_id,
                    event.lesson_id, event.exercise_id,
                    json.dumps(event.concept_ids, ensure_ascii=False),
                    event.outcome, event.score, event.max_score,
                    json.dumps(event.payload, ensure_ascii=False),
                    event.source, event.created_at, event.supersedes,
                ),
            )

    def list(
        self,
        lesson_id: str | None = None,
        concept_id: str | None = None,
        limit: int = 100,
    ) -> list[EvidenceEvent]:
        sql = "SELECT * FROM evidence WHERE 1=1"
        params: list[Any] = []
        if lesson_id:
            sql += " AND lesson_id = ?"
            params.append(lesson_id)
        if concept_id:
            sql += " AND concept_ids LIKE ?"
            params.append(f'%"{concept_id}"%')
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def count(self, lesson_id: str | None = None) -> int:
        sql = "SELECT COUNT(*) FROM evidence"
        params: list[Any] = []
        if lesson_id:
            sql += " WHERE lesson_id = ?"
            params.append(lesson_id)
        with sqlite3.connect(self.path) as conn:
            return int(conn.execute(sql, params).fetchone()[0])

    def export_jsonl(self, path: Path) -> int:
        events = self.list(limit=1_000_000)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return len(events)

    def import_jsonl(self, path: Path) -> int:
        inserted = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = EvidenceEvent(**json.loads(line))
            before = self.count()
            self.append(event)
            if self.count() > before:
                inserted += 1
        return inserted

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> EvidenceEvent:
        return EvidenceEvent(
            id=row["id"],
            learner_id=row["learner_id"],
            kind=row["kind"],
            concept_ids=json.loads(row["concept_ids"]),
            payload=json.loads(row["payload"]),
            source=row["source"],
            created_at=row["created_at"],
            session_id=row["session_id"],
            lesson_id=row["lesson_id"],
            exercise_id=row["exercise_id"],
            outcome=row["outcome"],
            score=row["score"],
            max_score=row["max_score"],
            supersedes=row["supersedes"],
        )
```

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest tests/test_evidence_store.py -q
git add src/testbridge/evidence/store.py tests/test_evidence_store.py
git commit -m "feat: append-only SQLite evidence store"
```

Expected: all tests pass.

---

## Task 8: Lesson Renderer

**Files:**
- Create: `src/testbridge/lesson/renderer.py`
- Test: `tests/test_lesson_renderer.py`

**Interfaces:**
- Produces: `LessonView`, `WidgetView`, `render_exercise_form(exercise)`, `render_lesson(pack, lesson_id)`.
- `LessonView` fields: `lesson`, `module`, `concepts`, `exercises`, `resources`, `widgets`, `body_html`, `prev_lesson`, `next_lesson`.

- [ ] **Step 1: Write failing renderer tests**

```python
from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.lesson.renderer import render_lesson

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


def test_render_replaces_placeholders() -> None:
    pack = load_pack(FIXTURE)
    view = render_lesson(pack, "L-ONE")
    assert "tb-manifest" not in view.body_html
    assert 'form class="tb-exercise"' in view.body_html
    assert "data-exercise-id=\"EX-ONE\"" in view.body_html
    assert "tb-widget-canvas" in view.body_html
    assert "{{offset}}" in view.body_html


def test_render_resolves_refs() -> None:
    pack = load_pack(FIXTURE)
    view = render_lesson(pack, "L-ONE")
    assert view.module.id == "M01"
    assert [item.id for item in view.concepts] == ["c-one"]
    assert [item.id for item in view.exercises] == ["EX-ONE"]
    assert [item.id for item in view.resources] == ["DOC-ONE"]
    assert view.widgets[0].widget.id == "W-ONE"
    assert view.prev_lesson is None and view.next_lesson is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_lesson_renderer.py -q
```

Expected: import error.

- [ ] **Step 3: Implement `renderer.py`**

```python
"""Render a validated lesson into a shell-ready view."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from testbridge.contract.models import Concept, Exercise, Module, Resource, Widget
from testbridge.contract.sanitize import sanitize_fragment
from testbridge.content.repository import ContentPack, Lesson


@dataclass(frozen=True)
class WidgetView:
    widget: Widget
    template_html: str


@dataclass(frozen=True)
class LessonView:
    lesson: Lesson
    module: Module
    concepts: list[Concept]
    exercises: list[Exercise]
    resources: list[Resource]
    widgets: list[WidgetView]
    body_html: str
    prev_lesson: Lesson | None
    next_lesson: Lesson | None


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_exercise_form(exercise: Exercise) -> str:
    if exercise.type == "single_choice":
        fields = "".join(
            f'<label><input type="radio" name="answer" value="{_esc(option.id)}"> {_esc(option.text)}</label>'
            for option in exercise.options
        )
    elif exercise.type == "multi_choice":
        fields = "".join(
            f'<label><input type="checkbox" name="answer" value="{_esc(option.id)}"> {_esc(option.text)}</label>'
            for option in exercise.options
        )
    elif exercise.type == "short_answer":
        fields = '<textarea name="answer" rows="4" placeholder="用自己的话回答"></textarea>'
    elif exercise.type == "self_assess":
        fields = "".join(
            f'<label><input type="checkbox" name="checked" value="{_esc(item.dimension)}"> '
            f"{_esc(item.dimension)}：{_esc(item.criteria)}</label>"
            for item in exercise.rubric
        )
    else:
        fields = (
            '<input type="text" name="path" placeholder="附件路径，例如 data/artifacts/run.log">'
            '<textarea name="notes" rows="3" placeholder="观察与结论"></textarea>'
            '<div class="tb-self-check">'
            + "".join(
                f'<label><input type="checkbox" name="checked" value="{_esc(item.dimension)}"> '
                f"{_esc(item.dimension)}：{_esc(item.criteria)}</label>"
                for item in exercise.rubric
            )
            + "</div>"
        )

    hints = "".join(
        f'<p class="tb-hint" data-level="{hint.level}" hidden>{_esc(hint.text)}</p>'
        for hint in exercise.hints
    )
    return f"""<form class="tb-exercise" data-exercise-id="{_esc(exercise.id)}" data-exercise-type="{exercise.type}">
  <p class="tb-prompt">{_esc(exercise.prompt)}</p>
  <div class="tb-fields">{fields}</div>
  <div class="tb-actions"><button type="submit">提交</button><button type="button" class="tb-hint-button">提示</button></div>
  <div class="tb-hints">{hints}</div>
  <div class="tb-feedback" hidden></div>
</form>"""


def render_widget(widget: Widget, template_html: str) -> str:
    controls = "".join(
        f'<label>{_esc(parameter.label)} '
        f'<input type="range" data-param="{_esc(parameter.id)}" '
        f'min="{parameter.min}" max="{parameter.max}" value="{parameter.default}" step="any">'
        f"<output>{parameter.default}</output></label>"
        for parameter in widget.spec.parameters
    )
    rendered = template_html
    for parameter in widget.spec.parameters:
        rendered = rendered.replace("{{" + parameter.id + "}}", str(parameter.default))
    return f"""<figure class="tb-widget" data-widget-id="{_esc(widget.id)}">
  <div class="tb-widget-controls">{controls}</div>
  <div class="tb-widget-canvas">{rendered}</div>
  <template class="tb-widget-template">{template_html}</template>
  <figcaption>{_esc(widget.caption)}</figcaption>
</figure>"""


def render_lesson(pack: ContentPack, lesson_id: str) -> LessonView:
    lesson = pack.lesson(lesson_id)
    manifest = lesson.manifest
    body = sanitize_fragment(lesson.body_html)
    exercises = [pack.exercise(item) for item in manifest.exercises]
    resources = [pack.resource(item) for item in manifest.resources]
    concepts = [pack.concept(item) for item in manifest.concepts]

    widget_ids = list(dict.fromkeys(re.findall(r'data-tb-widget="([^"]+)"', body)))
    widgets: list[WidgetView] = []
    for widget_id in widget_ids:
        widget = pack.widget(widget_id)
        template_path = pack.root / widget.spec.template
        widgets.append(
            WidgetView(widget=widget, template_html=template_path.read_text(encoding="utf-8"))
        )

    for exercise in exercises:
        pattern = re.compile(
            rf'<div\b[^>]*data-tb-exercise="{re.escape(exercise.id)}"[^>]*>\s*</div>',
            re.IGNORECASE,
        )
        body = pattern.sub(render_exercise_form(exercise), body)

    for view in widgets:
        pattern = re.compile(
            rf'<div\b[^>]*data-tb-widget="{re.escape(view.widget.id)}"[^>]*>\s*</div>',
            re.IGNORECASE,
        )
        body = pattern.sub(render_widget(view.widget, view.template_html), body)

    prev_lesson, next_lesson = pack.prev_next(lesson_id)
    return LessonView(
        lesson=lesson,
        module=pack.modules[manifest.module],
        concepts=concepts,
        exercises=exercises,
        resources=resources,
        widgets=widgets,
        body_html=body,
        prev_lesson=prev_lesson,
        next_lesson=next_lesson,
    )
```

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest tests/test_lesson_renderer.py -q
git add src/testbridge/lesson/renderer.py tests/test_lesson_renderer.py
git commit -m "feat: render lessons with mounted exercises and widgets"
```

Expected: all tests pass.

---

## Task 9: FastAPI Lesson and Evidence API

**Files:**
- Create: `web/app.py`
- Create: `web/templates/base.html`
- Create: `web/templates/dashboard.html`
- Create: `web/templates/lesson.html`
- Create: `web/templates/progress.html`
- Create: `web/static/tb.css`
- Test: `tests/test_web.py`

**Interfaces:**
- Produces: `create_app(pack_dir=None, db_path=None) -> FastAPI`.
- Routes: `GET /`, `GET /lesson/{id}`, `GET /progress`, `GET /api/health`, `POST /api/evidence`, static `/assets/*`.

- [ ] **Step 1: Write failing web tests**

```python
from pathlib import Path

from fastapi.testclient import TestClient

from web.app import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(FIXTURE, tmp_path / "test.db"))


def test_dashboard(tmp_path: Path) -> None:
    response = client(tmp_path).get("/")
    assert response.status_code == 200
    assert "Demo Module" in response.text


def test_lesson_page(tmp_path: Path) -> None:
    response = client(tmp_path).get("/lesson/L-ONE")
    assert response.status_code == 200
    assert "Pick A." in response.text
    assert "tb-runtime.js" in response.text


def test_submit_evidence(tmp_path: Path) -> None:
    response = client(tmp_path).post(
        "/api/evidence",
        json={"lesson_id": "L-ONE", "exercise_id": "EX-ONE", "response": "a"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["grade"]["correct"] is True
    assert payload["evidence_id"]


def test_progress_page(tmp_path: Path) -> None:
    c = client(tmp_path)
    c.post("/api/evidence", json={"lesson_id": "L-ONE", "exercise_id": "EX-ONE", "response": "a"})
    response = c.get("/progress")
    assert response.status_code == 200
    assert "EX-ONE" in response.text


def test_unknown_lesson_is_404(tmp_path: Path) -> None:
    assert client(tmp_path).get("/lesson/NOPE").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_web.py -q
```

Expected: import error or missing template.

- [ ] **Step 3: Implement templates and CSS**

`web/templates/base.html`:

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}TestBridge{% endblock %}</title>
  <link rel="stylesheet" href="/static/tb.css">
</head>
<body data-lesson-id="{% block lesson_id %}{% endblock %}">
  <header class="tb-top">
    <a href="/" class="tb-brand">TestBridge</a>
    <nav><a href="/">课程</a><a href="/progress">进度</a></nav>
  </header>
  <main class="tb-main">{% block content %}{% endblock %}</main>
  {% block scripts %}{% endblock %}
</body>
</html>
```

`web/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}课程 · TestBridge{% endblock %}
{% block content %}
<h1>{{ pack.meta.title }}</h1>
<p>{{ pack.meta.description }}</p>
{% for module in modules %}
<section class="tb-module">
  <h2>{{ module.title }}</h2>
  <ul>
  {% for lesson in lessons_by_module[module.id] %}
    <li><a href="/lesson/{{ lesson.manifest.id }}">{{ lesson.manifest.title }}</a> · {{ lesson.manifest.minutes }} 分钟</li>
  {% endfor %}
  </ul>
</section>
{% endfor %}
{% endblock %}
```

`web/templates/lesson.html`:

```html
{% extends "base.html" %}
{% block title %}{{ view.lesson.manifest.title }} · TestBridge{% endblock %}
{% block lesson_id %}{{ view.lesson.manifest.id }}{% endblock %}
{% block content %}
<nav class="tb-breadcrumb">{{ view.module.title }}</nav>
<h1>{{ view.lesson.manifest.title }}</h1>
<p class="tb-meta">{{ view.lesson.manifest.minutes }} 分钟 · {{ view.lesson.manifest.target_level }}</p>
<ul class="tb-objectives">{% for item in view.lesson.manifest.objectives %}<li>{{ item }}</li>{% endfor %}</ul>
<article class="tb-lesson">{{ view.body_html | safe }}</article>
<aside class="tb-resources">
  <h2>资源</h2>
  <ul>{% for item in view.resources %}<li><a href="{{ item.url }}" target="_blank" rel="noopener noreferrer">{{ item.title }}</a> <span class="tb-trust">{{ item.trust }}</span></li>{% endfor %}</ul>
</aside>
<nav class="tb-pager">
  {% if view.prev_lesson %}<a href="/lesson/{{ view.prev_lesson.manifest.id }}">← {{ view.prev_lesson.manifest.title }}</a>{% endif %}
  {% if view.next_lesson %}<a href="/lesson/{{ view.next_lesson.manifest.id }}">{{ view.next_lesson.manifest.title }} →</a>{% endif %}
</nav>
{% endblock %}
{% block scripts %}
<script id="tb-exercise-data" type="application/json">{{ exercise_data | safe }}</script>
<script src="/static/tb-runtime.js"></script>
{% endblock %}
```

`web/templates/progress.html`:

```html
{% extends "base.html" %}
{% block title %}进度 · TestBridge{% endblock %}
{% block content %}
<h1>进度</h1>
<p>共 {{ events|length }} 条证据。</p>
<table>
<tr><th>时间</th><th>课程</th><th>练习</th><th>结果</th><th>分数</th></tr>
{% for event in events %}
<tr><td>{{ event.created_at }}</td><td>{{ event.lesson_id or "" }}</td><td>{{ event.exercise_id or "" }}</td><td>{{ event.outcome or "" }}</td><td>{{ event.score if event.score is not none else "" }}</td></tr>
{% endfor %}
</table>
{% endblock %}
```

`web/static/tb.css`:

```css
:root { --ink: #1f2937; --muted: #6b7280; --line: #e5e7eb; --accent: #2563eb; --bg: #ffffff; }
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: var(--ink); background: var(--bg); line-height: 1.65; }
.tb-top { display: flex; justify-content: space-between; padding: 1rem 2rem; border-bottom: 1px solid var(--line); }
.tb-brand { font-weight: 700; color: var(--ink); text-decoration: none; }
.tb-top nav a { margin-left: 1rem; color: var(--muted); text-decoration: none; }
.tb-main { max-width: 860px; margin: 0 auto; padding: 2rem 1.25rem 5rem; }
.tb-lesson h1 { margin-top: 0; }
.tb-meta, .tb-breadcrumb { color: var(--muted); font-size: .9rem; }
.tb-objectives { background: #f8fafc; border-left: 4px solid var(--accent); padding: 1rem 1.25rem 1rem 2rem; }
.tb-exercise { border: 1px solid var(--line); border-radius: 8px; padding: 1rem; margin: 1.5rem 0; }
.tb-fields label { display: block; margin: .4rem 0; }
.tb-fields textarea, .tb-fields input[type="text"] { width: 100%; padding: .5rem; border: 1px solid var(--line); border-radius: 6px; }
.tb-actions { margin-top: .8rem; }
.tb-actions button { margin-right: .5rem; padding: .45rem .9rem; border: 1px solid var(--line); border-radius: 6px; background: #fff; cursor: pointer; }
.tb-feedback { margin-top: .8rem; padding: .6rem .8rem; background: #f8fafc; border-radius: 6px; }
.tb-feedback[data-outcome="correct"] { background: #ecfdf5; }
.tb-feedback[data-outcome="incorrect"] { background: #fef2f2; }
.tb-widget { border: 1px solid var(--line); border-radius: 8px; padding: 1rem; margin: 1.5rem 0; }
.tb-widget-controls label { display: block; margin: .4rem 0; }
.tb-widget-canvas svg { width: 100%; height: auto; }
.tb-resources { margin-top: 3rem; border-top: 1px solid var(--line); padding-top: 1rem; }
.tb-trust { color: var(--muted); font-size: .8rem; border: 1px solid var(--line); padding: 0 .3rem; border-radius: 4px; }
.tb-pager { display: flex; justify-content: space-between; margin-top: 3rem; }
.tb-pager a { color: var(--accent); text-decoration: none; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; border-bottom: 1px solid var(--line); padding: .5rem; }
```

- [ ] **Step 4: Implement `web/app.py`**

```python
"""FastAPI surfaces for lessons, exercises, and evidence."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.exercise.grading import grade
from testbridge.lesson.renderer import render_lesson

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent


class EvidenceRequest(BaseModel):
    lesson_id: str
    exercise_id: str
    response: Any = None
    hints_used: int = 0
    duration_ms: int = 0
    session_id: str | None = None


def create_app(pack_dir: Path | None = None, db_path: Path | None = None) -> FastAPI:
    pack_path = pack_dir or ROOT / "content-packs" / "sample-sensors"
    database = db_path or ROOT / "data" / "testbridge.db"
    pack = load_pack(pack_path)
    store = EvidenceStore(database)

    app = FastAPI(title="TestBridge")
    app.state.pack = pack
    app.state.store = store
    templates = Jinja2Templates(directory=str(BASE / "templates"))
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
    assets_dir = pack.root / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    def ctx(request: Request, **kwargs):
        return {"request": request, "pack": pack, **kwargs}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        modules = sorted(pack.modules.values(), key=lambda item: (item.order, item.id))
        lessons_by_module = {
            module.id: [pack.lessons[item] for item in module.lessons if item in pack.lessons]
            for module in modules
        }
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context=ctx(request, modules=modules, lessons_by_module=lessons_by_module),
        )

    @app.get("/lesson/{lesson_id}", response_class=HTMLResponse)
    def lesson_page(request: Request, lesson_id: str):
        if lesson_id not in pack.lessons:
            raise HTTPException(status_code=404, detail="lesson not found")
        view = render_lesson(pack, lesson_id)
        exercise_data = json.dumps(
            {exercise.id: exercise.model_dump(mode="json") for exercise in view.exercises},
            ensure_ascii=False,
        )
        return templates.TemplateResponse(
            request=request,
            name="lesson.html",
            context=ctx(request, view=view, exercise_data=exercise_data),
        )

    @app.get("/progress", response_class=HTMLResponse)
    def progress_page(request: Request):
        events = store.list(limit=200)
        return templates.TemplateResponse(
            request=request, name="progress.html", context=ctx(request, events=events)
        )

    @app.post("/api/evidence")
    def submit_evidence(payload: EvidenceRequest):
        if payload.lesson_id not in pack.lessons:
            raise HTTPException(status_code=404, detail="lesson not found")
        exercise = pack.exercises.get(payload.exercise_id)
        if exercise is None:
            raise HTTPException(status_code=404, detail="exercise not found")
        result = grade(exercise, payload.response)
        event = new_event(
            kind="exercise_attempt",
            lesson_id=payload.lesson_id,
            exercise_id=payload.exercise_id,
            concept_ids=exercise.concepts,
            outcome=result.outcome,
            score=result.score,
            max_score=result.max_score,
            payload={
                "response": payload.response,
                "hints_used": payload.hints_used,
                "duration_ms": payload.duration_ms,
                "feedback": result.feedback,
                "details": result.details,
            },
            source="web",
            session_id=payload.session_id,
        )
        store.append(event)
        return {"evidence_id": event.id, "grade": asdict(result)}

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app
```

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest tests/test_web.py -q
git add web tests/test_web.py
git commit -m "feat: serve lessons and record evidence"
```

Expected: all tests pass.

---

## Task 10: Browser Runtime for Submit, Hints, and Widgets

**Files:**
- Create: `web/static/tb-runtime.js`
- Test: `tests/test_web.py` (extend with a static-file assertion)

**Interfaces:**
- Consumes: `form.tb-exercise[data-exercise-id]`, `#tb-exercise-data`, `body[data-lesson-id]`, `.tb-widget`.
- Produces: `POST /api/evidence` calls; progressive hint reveal; widget parameter updates.

- [ ] **Step 1: Add a failing assertion**

Append to `tests/test_web.py`:

```python
def test_runtime_script_is_served(tmp_path: Path) -> None:
    response = client(tmp_path).get("/static/tb-runtime.js")
    assert response.status_code == 200
    assert "/api/evidence" in response.text
    assert "tb-widget-template" in response.text
```

- [ ] **Step 2: Run it to verify it fails**

```bash
python -m pytest tests/test_web.py::test_runtime_script_is_served -q
```

Expected: 404 because the file does not exist.

- [ ] **Step 3: Implement `web/static/tb-runtime.js`**

```javascript
(function () {
  const lessonId = document.body.dataset.lessonId || "";
  const dataEl = document.getElementById("tb-exercise-data");
  const exercises = dataEl ? JSON.parse(dataEl.textContent) : {};

  function collect(form, type) {
    if (type === "single_choice") {
      const el = form.querySelector('input[name="answer"]:checked');
      return el ? el.value : null;
    }
    if (type === "multi_choice") {
      return Array.from(form.querySelectorAll('input[name="answer"]:checked')).map((el) => el.value);
    }
    if (type === "short_answer") {
      return form.querySelector('textarea[name="answer"]').value;
    }
    if (type === "self_assess") {
      return { checked: Array.from(form.querySelectorAll('input[name="checked"]:checked')).map((el) => el.value) };
    }
    if (type === "artifact") {
      return {
        path: form.querySelector('input[name="path"]').value,
        notes: form.querySelector('textarea[name="notes"]').value,
        checked: Array.from(form.querySelectorAll('input[name="checked"]:checked')).map((el) => el.value),
      };
    }
    return null;
  }

  document.querySelectorAll("form.tb-exercise").forEach((form) => {
    let hintsUsed = 0;
    const startedAt = Date.now();
    const hintButton = form.querySelector(".tb-hint-button");
    if (hintButton) {
      hintButton.addEventListener("click", () => {
        const next = Array.from(form.querySelectorAll(".tb-hint[hidden]"))[0];
        if (next) {
          next.hidden = false;
          hintsUsed += 1;
        } else {
          hintButton.disabled = true;
          hintButton.textContent = "没有更多提示";
        }
      });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const type = form.dataset.exerciseType;
      const response = collect(form, type);
      const feedback = form.querySelector(".tb-feedback");
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      try {
        const res = await fetch("/api/evidence", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            lesson_id: lessonId,
            exercise_id: form.dataset.exerciseId,
            response,
            hints_used: hintsUsed,
            duration_ms: Date.now() - startedAt,
          }),
        });
        if (!res.ok) throw new Error(await res.text());
        const payload = await res.json();
        feedback.hidden = false;
        feedback.dataset.outcome = payload.grade.outcome;
        feedback.textContent = payload.grade.feedback;
      } catch (err) {
        feedback.hidden = false;
        feedback.textContent = "提交失败：" + err.message;
        button.disabled = false;
      }
    });
  });

  document.querySelectorAll(".tb-widget").forEach((widget) => {
    const template = widget.querySelector("template.tb-widget-template");
    const canvas = widget.querySelector(".tb-widget-canvas");
    if (!template || !canvas) return;
    const inputs = Array.from(widget.querySelectorAll("input[data-param]"));
    function render() {
      let html = template.innerHTML;
      inputs.forEach((input) => {
        html = html.split("{{" + input.dataset.param + "}}").join(input.value);
        const output = input.parentElement.querySelector("output");
        if (output) output.textContent = input.value;
      });
      canvas.innerHTML = html;
    }
    inputs.forEach((input) => input.addEventListener("input", render));
    render();
  });
})();
```

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest tests/test_web.py -q
git add web/static/tb-runtime.js tests/test_web.py
git commit -m "feat: add browser runtime for exercises and widgets"
```

Expected: all tests pass.

---

## Task 11: CLI and Standalone Build

**Files:**
- Create: `src/testbridge/cli.py`
- Create: `src/testbridge/build.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_build.py`

**Interfaces:**
- Produces: `main(argv=None) -> int`; `build_pack(pack_dir, out_dir, lesson_id=None) -> list[Path]`.
- Commands: `validate`, `build`, `serve`, `list`, `evidence-export`, `evidence-import`.

- [ ] **Step 1: Write failing CLI and build tests**

`tests/test_cli.py`:

```python
from pathlib import Path

from testbridge.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


def test_validate_ok(capsys) -> None:
    assert main(["validate", str(FIXTURE)]) == 0
    assert "0 error" in capsys.readouterr().out


def test_validate_missing(tmp_path: Path) -> None:
    assert main(["validate", str(tmp_path / "nope")]) == 1


def test_evidence_round_trip(tmp_path: Path, capsys) -> None:
    from testbridge.evidence.store import EvidenceStore, new_event

    db = tmp_path / "e.db"
    store = EvidenceStore(db)
    store.append(new_event(kind="exercise_attempt", concept_ids=["c-one"]))
    out = tmp_path / "e.jsonl"
    assert main(["evidence-export", str(db), str(out)]) == 0
    assert out.is_file()
    assert main(["evidence-import", str(db), str(out)]) == 0
```

`tests/test_build.py`:

```python
from pathlib import Path

from testbridge.build import build_pack

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"


def test_build_creates_standalone(tmp_path: Path) -> None:
    paths = build_pack(FIXTURE, tmp_path)
    assert len(paths) == 1
    html = paths[0].read_text(encoding="utf-8")
    assert "Demo Lesson" in html
    assert "TB_EXERCISES" in html
    assert "localStorage" in html
    assert "tb-exercise" in html
    assert (tmp_path / "fixture" / "assets" / "widgets" / "demo.svg").is_file()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_cli.py tests/test_build.py -q
```

Expected: import errors.

- [ ] **Step 3: Implement `build.py`**

```python
"""Build standalone, offline HTML lessons."""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.lesson.renderer import render_lesson

STANDALONE_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__</style>
</head>
<body data-lesson-id="__LESSON_ID__">
<main class="tb-main">
__BODY__
<button id="tb-export">导出证据 JSONL</button>
</main>
<script>const TB_EXERCISES = __DATA__; const TB_LESSON_ID = "__LESSON_ID__";</script>
<script>__JS__</script>
</body>
</html>
"""

STANDALONE_JS = r"""
(function () {
  const KEY = "tb-evidence";
  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; }
  }
  function save(rows) { localStorage.setItem(KEY, JSON.stringify(rows)); }
  function norm(value) {
    return String(value || "").toLowerCase().replace(/[\s,，。.!！?？;；:：、"'“”‘’()（）\[\]【】]/g, "");
  }
  function grade(ex, response) {
    if (ex.type === "single_choice") {
      const ok = response === ex.answer;
      return { outcome: ok ? "correct" : "incorrect", correct: ok, score: ok ? 1 : 0, max_score: 1,
               feedback: ok ? "回答正确。" : "再想想。" };
    }
    if (ex.type === "multi_choice") {
      const expected = new Set(ex.answer || []);
      const selected = new Set(response || []);
      let hits = 0;
      expected.forEach((item) => { if (selected.has(item)) hits += 1; });
      const score = expected.size ? hits / expected.size : 0;
      const ok = hits === expected.size && selected.size === expected.size;
      return { outcome: ok ? "correct" : (hits ? "partial" : "incorrect"), correct: ok, score: score, max_score: 1,
               feedback: ok ? "全对。" : "命中了 " + hits + "/" + expected.size + " 个正确项。" };
    }
    if (ex.type === "short_answer") {
      const text = norm(response);
      const accepted = ex.answer.accepted || [];
      const matched = accepted.filter((item) => text.includes(norm(item)));
      const ok = matched.length >= (ex.answer.min_hits || 1);
      return { outcome: ok ? "correct" : "incorrect", correct: ok, score: accepted.length ? matched.length / accepted.length : 0, max_score: 1,
               feedback: ok ? "命中关键点。" : "关键点不足。" };
    }
    if (ex.type === "self_assess") {
      const checked = new Set((response && response.checked) || []);
      const score = (ex.rubric || []).reduce((sum, item) => sum + (checked.has(item.dimension) ? item.weight : 0), 0);
      return { outcome: "submitted", correct: null, score: score, max_score: 1, feedback: "已记录自评。" };
    }
    if (!response || !String(response.path || "").trim()) {
      return { outcome: "incorrect", correct: false, score: 0, max_score: 1, feedback: "请填写附件路径。" };
    }
    const checked = new Set((response && response.checked) || []);
    const score = (ex.rubric || []).reduce((sum, item) => sum + (checked.has(item.dimension) ? item.weight : 0), 0);
    return { outcome: "submitted", correct: null, score: score, max_score: 1, feedback: "已记录产出物。" };
  }
  document.querySelectorAll("form.tb-exercise").forEach((form) => {
    const startedAt = Date.now();
    let hintsUsed = 0;
    const hintButton = form.querySelector(".tb-hint-button");
    if (hintButton) {
      hintButton.addEventListener("click", () => {
        const next = Array.from(form.querySelectorAll(".tb-hint[hidden]"))[0];
        if (next) { next.hidden = false; hintsUsed += 1; }
        else { hintButton.disabled = true; hintButton.textContent = "没有更多提示"; }
      });
    }
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const type = form.dataset.exerciseType;
      let response = null;
      if (type === "single_choice") {
        const el = form.querySelector('input[name="answer"]:checked');
        response = el ? el.value : null;
      } else if (type === "multi_choice") {
        response = Array.from(form.querySelectorAll('input[name="answer"]:checked')).map((el) => el.value);
      } else if (type === "short_answer") {
        response = form.querySelector('textarea[name="answer"]').value;
      } else if (type === "self_assess") {
        response = { checked: Array.from(form.querySelectorAll('input[name="checked"]:checked')).map((el) => el.value) };
      } else {
        response = {
          path: form.querySelector('input[name="path"]').value,
          notes: form.querySelector('textarea[name="notes"]').value,
          checked: Array.from(form.querySelectorAll('input[name="checked"]:checked')).map((el) => el.value),
        };
      }
      const result = grade(TB_EXERCISES[form.dataset.exerciseId], response);
      const feedback = form.querySelector(".tb-feedback");
      feedback.hidden = false;
      feedback.dataset.outcome = result.outcome;
      feedback.textContent = result.feedback;
      const exercise = TB_EXERCISES[form.dataset.exerciseId];
      const rows = load();
      rows.push({
        id: Date.now().toString(36) + Math.random().toString(36).slice(2),
        learner_id: "local",
        kind: "exercise_attempt",
        concept_ids: exercise.concepts || [],
        payload: { response: response, hints_used: hintsUsed, duration_ms: Date.now() - startedAt },
        source: "standalone",
        created_at: new Date().toISOString(),
        session_id: null,
        lesson_id: TB_LESSON_ID,
        exercise_id: form.dataset.exerciseId,
        outcome: result.outcome,
        score: result.score,
        max_score: result.max_score,
        supersedes: null,
      });
      save(rows);
      form.querySelector('button[type="submit"]').disabled = true;
    });
  });
  document.getElementById("tb-export").addEventListener("click", () => {
    const lines = load().map((row) => JSON.stringify(row)).join("\n") + "\n";
    const blob = new Blob([lines], { type: "application/x-ndjson" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "tb-evidence.jsonl";
    link.click();
  });
  document.querySelectorAll(".tb-widget").forEach((widget) => {
    const template = widget.querySelector("template.tb-widget-template");
    const canvas = widget.querySelector(".tb-widget-canvas");
    if (!template || !canvas) return;
    const inputs = Array.from(widget.querySelectorAll("input[data-param]"));
    function render() {
      let markup = template.innerHTML;
      inputs.forEach((input) => {
        markup = markup.split("{{" + input.dataset.param + "}}").join(input.value);
        const output = input.parentElement.querySelector("output");
        if (output) output.textContent = input.value;
      });
      canvas.innerHTML = markup;
    }
    inputs.forEach((input) => input.addEventListener("input", render));
    render();
  });
})();
"""


def build_pack(pack_dir: Path, out_dir: Path, lesson_id: str | None = None) -> list[Path]:
    pack = load_pack(pack_dir)
    target_root = out_dir / pack.meta.id
    lessons = [pack.lessons[lesson_id]] if lesson_id else pack.lessons_in_order()
    css = (Path(__file__).resolve().parents[2] / "web" / "static" / "tb.css").read_text(encoding="utf-8")

    written: list[Path] = []
    for lesson in lessons:
        view = render_lesson(pack, lesson.manifest.id)
        relative = Path("modules") / lesson.manifest.module / "lessons" / f"{lesson.manifest.id}.html"
        path = target_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {exercise.id: exercise.model_dump(mode="json") for exercise in view.exercises}
        values = {
            "TITLE": html.escape(lesson.manifest.title),
            "LESSON_ID": lesson.manifest.id,
            "CSS": css,
            "DATA": json.dumps(data, ensure_ascii=False),
            "JS": STANDALONE_JS,
            "BODY": view.body_html,
        }
        document = re.sub(
            r"__(TITLE|LESSON_ID|CSS|DATA|JS|BODY)__",
            lambda match: values[match.group(1)],
            STANDALONE_TEMPLATE,
        )
        path.write_text(document, encoding="utf-8")
        written.append(path)

    assets = pack.root / "assets"
    if assets.is_dir():
        shutil.copytree(assets, target_root / "assets", dirs_exist_ok=True)

    manifest = {
        "pack": pack.meta.model_dump(mode="json", by_alias=True),
        "lessons": [item.manifest.id for item in lessons],
    }
    (target_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return written
```

- [ ] **Step 4: Implement `cli.py`**

```python
"""Command-line interface for TestBridge."""

from __future__ import annotations

import argparse
from pathlib import Path

from testbridge.build import build_pack
from testbridge.contract.validator import validate_pack
from testbridge.content.repository import list_packs
from testbridge.evidence.store import EvidenceStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tb")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a content pack")
    validate.add_argument("pack")

    build = sub.add_parser("build", help="build standalone lessons")
    build.add_argument("pack")
    build.add_argument("--out", default="dist")
    build.add_argument("--lesson", default=None)

    serve = sub.add_parser("serve", help="run the web app")
    serve.add_argument("pack")
    serve.add_argument("--db", default="data/testbridge.db")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    listing = sub.add_parser("list", help="list packs under a root")
    listing.add_argument("root", default="content-packs", nargs="?")

    export = sub.add_parser("evidence-export")
    export.add_argument("db")
    export.add_argument("out")

    import_cmd = sub.add_parser("evidence-import")
    import_cmd.add_argument("db")
    import_cmd.add_argument("path")

    args = parser.parse_args(argv)

    if args.command == "validate":
        report = validate_pack(Path(args.pack))
        for issue in report.errors:
            print(f"ERROR {issue.code}: {issue.message}")
        for issue in report.warnings:
            print(f"WARN {issue.code}: {issue.message}")
        print(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)")
        return 0 if report.ok else 1

    if args.command == "build":
        paths = build_pack(Path(args.pack), Path(args.out), args.lesson)
        for path in paths:
            print(path)
        return 0

    if args.command == "serve":
        import uvicorn

        from web.app import create_app

        uvicorn.run(create_app(Path(args.pack), Path(args.db)), host=args.host, port=args.port)
        return 0

    if args.command == "list":
        for info in list_packs(Path(args.root)):
            print(f"{info.meta.id}\t{info.meta.version}\t{info.path}")
        return 0

    if args.command == "evidence-export":
        count = EvidenceStore(Path(args.db)).export_jsonl(Path(args.out))
        print(f"exported {count}")
        return 0

    if args.command == "evidence-import":
        count = EvidenceStore(Path(args.db)).import_jsonl(Path(args.path))
        print(f"imported {count}")
        return 0

    return 1
```

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest tests/test_cli.py tests/test_build.py -q
git add src/testbridge/cli.py src/testbridge/build.py tests/test_cli.py tests/test_build.py
git commit -m "feat: add CLI and standalone build"
```

Expected: all tests pass.

---

## Task 12: Sample Content Pack

**Files:**
- Create: `content-packs/sample-sensors/pack.yaml`
- Create: `content-packs/sample-sensors/concepts.yaml`
- Create: `content-packs/sample-sensors/exercises.yaml`
- Create: `content-packs/sample-sensors/resources.yaml`
- Create: `content-packs/sample-sensors/widgets.yaml`
- Create: `content-packs/sample-sensors/modules/M01/module.yaml`
- Create: `content-packs/sample-sensors/modules/M01/lessons/L-SYNC-001.html`
- Create: `content-packs/sample-sensors/modules/M01/lessons/L-SYNC-002.html`
- Create: `content-packs/sample-sensors/modules/M01/lessons/L-SYNC-003.html`
- Create: `content-packs/sample-sensors/assets/figures/clock-offset.svg`
- Create: `content-packs/sample-sensors/assets/widgets/sync-offset.svg`
- Test: `tests/test_sample_pack.py`

**Interfaces:**
- Produces: a valid `sample-sensors` pack that exercises every P1 feature.

- [ ] **Step 1: Write the failing sample-pack test**

```python
from pathlib import Path

from testbridge.build import build_pack
from testbridge.contract.validator import validate_pack
from testbridge.content.repository import load_pack
from testbridge.lesson.renderer import render_lesson

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"


def test_sample_pack_is_valid() -> None:
    report = validate_pack(SAMPLE)
    assert report.ok, report.errors


def test_all_lessons_render() -> None:
    pack = load_pack(SAMPLE)
    assert len(pack.lessons) == 3
    for lesson in pack.lessons_in_order():
        view = render_lesson(pack, lesson.manifest.id)
        assert view.body_html
        assert "form class=\"tb-exercise\"" in view.body_html


def test_build_sample_pack(tmp_path: Path) -> None:
    paths = build_pack(SAMPLE, tmp_path)
    assert len(paths) == 3
    assert all(path.is_file() for path in paths)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
python -m pytest tests/test_sample_pack.py -q
```

Expected: `pack directory not found`.

- [ ] **Step 3: Write the pack metadata**

`content-packs/sample-sensors/pack.yaml`:

```yaml
schema: tb/1
id: sample-sensors
version: 0.1.0
title: 示例包：传感器时间同步
description: 用于验证 tb/1 契约与运行时的示例内容，不是最终课程。
language: zh-CN
license: CC-BY-4.0
authors: [testbridge]
created: 2026-10-24
fixture: true
```

- [ ] **Step 4: Write concepts, resources, exercises, widgets, and module**

`content-packs/sample-sensors/concepts.yaml`:

```yaml
schema: tb/1
concepts:
  - id: timestamp-basics
    title: 时间戳基础
    domain: sensors
    target_level: L1
    prerequisites: []
    weight: 0.5
    evidence_criteria:
      - {id: EV-TS-DEFINE, description: 能说出时间戳的组成与单位, level: L1}
    resources: [DOC-ROS2-TIME]

  - id: clock-drift
    title: 时钟漂移
    domain: sensors
    target_level: L2
    prerequisites: [timestamp-basics]
    weight: 0.5
    evidence_criteria:
      - {id: EV-DRIFT-EXPLAIN, description: 能解释漂移与固定偏移的区别, level: L2}
    resources: [DOC-PTP]

  - id: sensor-time-sync
    title: 传感器时间同步
    domain: sensors
    target_level: L3
    prerequisites: [timestamp-basics]
    related: [clock-drift]
    weight: 1.0
    evidence_criteria:
      - {id: EV-SYNC-EXPLAIN, description: 能解释时间戳、时钟源、同步误差的来源, level: L2}
      - {id: EV-SYNC-DESIGN, description: 能设计同步误差的测试方法与判定阈值, level: L3}
    resources: [DOC-ROS2-TIME, DOC-PTP]
```

`content-packs/sample-sensors/resources.yaml`:

```yaml
schema: tb/1
resources:
  - id: DOC-ROS2-TIME
    title: ROS 2 Time and Clock
    url: https://docs.ros.org/en/rolling/Concepts/About-Time.html
    type: official-doc
    trust: A
    license: Apache-2.0
    last_verified: 2026-10-24
    coverage: [timestamp-basics, sensor-time-sync]
    why: 解释 ROS 时间源、仿真时间与时钟类型，是同步测试的一手依据。

  - id: DOC-PTP
    title: IEEE 1588 Precision Time Protocol
    url: https://standards.ieee.org/ieee/1588/6825/
    type: standard
    trust: A
    license: IEEE
    last_verified: 2026-10-24
    coverage: [clock-drift, sensor-time-sync]
    why: 硬件时间同步的协议基础，理解主从时钟与偏移测量。

  - id: DOC-ROS2-BAG
    title: Recording and Playing Back Data
    url: https://docs.ros.org/en/rolling/Tutorials/Beginner-CLI-Tools/Recording-And-Playing-Back-Data/Recording-And-Playing-Back-Data.html
    type: tutorial
    trust: A
    license: Apache-2.0
    last_verified: 2026-10-24
    coverage: [sensor-time-sync]
    why: 用 rosbag2 采集带时间戳的数据，是同步测试的常用手段。

  - id: DOC-ROS2-QOS
    title: ROS 2 QoS Settings
    url: https://docs.ros.org/en/rolling/Concepts/About-Quality-of-Service-Settings.html
    type: official-doc
    trust: A
    license: Apache-2.0
    last_verified: 2026-10-24
    coverage: [sensor-time-sync]
    why: 传感器数据流的 QoS 会影响丢包与延迟，间接影响同步判断。

  - id: COURSE-TIME-SYNC
    title: Real-Time Systems: Clock Synchronization
    url: https://en.wikipedia.org/wiki/Clock_synchronization
    type: overview
    trust: B
    license: CC-BY-SA-4.0
    last_verified: 2026-10-24
    coverage: [clock-drift]
    why: 快速建立时钟同步的整体图景，关键结论回到 A 级资料。
```

`content-packs/sample-sensors/exercises.yaml`:

```yaml
schema: tb/1
exercises:
  - id: EX-SYNC-001
    type: single_choice
    concepts: [sensor-time-sync]
    level: L2
    prompt: 两个传感器时间戳相差 20ms，最不可能的根因是？
    options:
      - {id: a, text: 时钟源不同}
      - {id: b, text: 传输延迟}
      - {id: c, text: 采样频率不同}
      - {id: d, text: 驱动时间戳打点位置不同}
    answer: c
    explanation: 采样频率影响采样间隔，不直接造成固定时间偏移。
    hints:
      - {level: 1, text: 先区分“偏移”和“间隔”。}
      - {level: 2, text: 固定偏移通常来自时钟或打点位置。}
    difficulty: 2

  - id: EX-SYNC-002
    type: short_answer
    concepts: [sensor-time-sync]
    level: L3
    prompt: 写出一个验证两路传感器时间同步误差的测试方案。
    answer:
      accepted: ["时间戳对齐", "同一事件", "统计偏移", "阈值"]
      min_hits: 2
    rubric:
      - {dimension: 方法, weight: 0.4, criteria: 有可执行的对比方法}
      - {dimension: 判定, weight: 0.4, criteria: 有指标和阈值}
      - {dimension: 失败模式, weight: 0.2, criteria: 提到至少一种异常}
    hints:
      - {level: 1, text: 先找一个可同时被两路传感器观测的事件。}
    difficulty: 3

  - id: EX-SYNC-003
    type: self_assess
    concepts: [sensor-time-sync]
    level: L3
    prompt: 用自己的话解释“时钟漂移”和“固定偏移”的区别。
    rubric:
      - {dimension: 机制, weight: 0.5, criteria: 能区分随时间累积 vs 固定}
      - {dimension: 测试, weight: 0.5, criteria: 能说出对应的检测方法}

  - id: EX-SYNC-004
    type: artifact
    concepts: [sensor-time-sync]
    level: L3
    prompt: 提交一次同步误差测试的日志和判定结果。
    artifact:
      accept: [log, txt, png, md]
      max_size_mb: 10
    rubric:
      - {dimension: 可复现, weight: 0.4, criteria: 步骤和命令完整}
      - {dimension: 判定, weight: 0.4, criteria: 有指标和阈值}
      - {dimension: 分析, weight: 0.2, criteria: 解释了异常}

  - id: EX-SYNC-005
    type: multi_choice
    concepts: [clock-drift]
    level: L2
    prompt: 下列哪些会造成两路传感器时间戳不一致？
    options:
      - {id: a, text: 时钟源不同}
      - {id: b, text: 采样频率不同}
      - {id: c, text: 打点位置不同}
      - {id: d, text: 传输延迟不同}
    answer: [a, c, d]
    hints:
      - {level: 1, text: 先问“时间戳是在哪一刻生成的”。}
    difficulty: 2

  - id: EX-SYNC-006
    type: single_choice
    concepts: [timestamp-basics]
    level: L1
    prompt: 时间戳的核心作用是什么？
    options:
      - {id: a, text: 标识事件发生的时刻}
      - {id: b, text: 表示数据大小}
      - {id: c, text: 表示传感器精度}
    answer: a
    difficulty: 1
```

`content-packs/sample-sensors/widgets.yaml`:

```yaml
schema: tb/1
widgets:
  - id: W-SYNC-OFFSET
    type: parameter-svg
    title: 固定偏移 vs 漂移
    spec:
      template: assets/widgets/sync-offset.svg
      parameters:
        - {id: offset, label: 固定偏移(ms), min: -50, max: 50, default: 20}
        - {id: drift, label: 漂移幅度(倍), min: 0.2, max: 2.0, default: 0.5}
    caption: 调整参数，观察两路信号的对齐变化。
```

`content-packs/sample-sensors/modules/M01/module.yaml`:

```yaml
schema: tb/1
id: M01
title: 传感器时间同步
concepts: [timestamp-basics, clock-drift, sensor-time-sync]
lessons: [L-SYNC-001, L-SYNC-002, L-SYNC-003]
order: 1
```

- [ ] **Step 5: Write three lesson HTML fragments**

`content-packs/sample-sensors/modules/M01/lessons/L-SYNC-001.html`:

```html
<script type="application/json" id="tb-manifest">
{
  "schema": "tb/1",
  "id": "L-SYNC-001",
  "title": "时间戳、时钟源与同步误差",
  "module": "M01",
  "concepts": ["timestamp-basics", "sensor-time-sync"],
  "target_level": "L2",
  "minutes": 20,
  "objectives": ["区分固定偏移、漂移与抖动", "能说出时间戳的生成位置对同步的影响"],
  "prerequisites": [],
  "exercises": ["EX-SYNC-001", "EX-SYNC-003"],
  "resources": ["DOC-ROS2-TIME", "DOC-PTP"]
}
</script>
<article class="tb-lesson">
  <h1>时间戳、时钟源与同步误差</h1>
  <section>
    <p>时间戳不是一个“附加字段”，它记录了事件在某个时钟域里发生的时刻。两路传感器的时间戳能不能比较，取决于它们是否在同一个时钟域、是否在同一刻打点。</p>
    <p>先区分三件事：<strong>固定偏移</strong>是两条时间轴整体错开；<strong>漂移</strong>是错开量随运行时间累积；<strong>抖动</strong>是每次打点的短时波动。三者的测试方法不同。</p>
  </section>
  <figure>
    <img src="../../assets/figures/clock-offset.svg" alt="两路信号的时间偏移示意">
    <figcaption>固定偏移与漂移的直观差异。</figcaption>
  </figure>
  <div data-tb-widget="W-SYNC-OFFSET"></div>
  <section>
    <h2>测试视角</h2>
    <ul>
      <li>先确认两路数据是否使用同一时钟源。</li>
      <li>找一个可被两路同时观测的事件，比较时间戳差。</li>
      <li>连续采样，区分固定偏移与随时间增长的漂移。</li>
    </ul>
  </section>
  <div data-tb-exercise="EX-SYNC-001"></div>
  <div data-tb-exercise="EX-SYNC-003"></div>
</article>
```

`content-packs/sample-sensors/modules/M01/lessons/L-SYNC-002.html`:

```html
<script type="application/json" id="tb-manifest">
{
  "schema": "tb/1",
  "id": "L-SYNC-002",
  "title": "固定偏移、漂移与抖动",
  "module": "M01",
  "concepts": ["timestamp-basics", "clock-drift", "sensor-time-sync"],
  "target_level": "L2",
  "minutes": 20,
  "objectives": ["能解释三类同步误差的来源", "能根据现象选择测试方法"],
  "prerequisites": ["timestamp-basics"],
  "exercises": ["EX-SYNC-005", "EX-SYNC-006"],
  "resources": ["DOC-PTP", "DOC-ROS2-TIME"]
}
</script>
<article class="tb-lesson">
  <h1>固定偏移、漂移与抖动</h1>
  <section>
    <p>固定偏移通常来自时钟源不同或打点位置不同；漂移来自两个时钟频率不完全一致；抖动来自调度、传输或中断的短时不确定性。</p>
    <p>面试里常被追问：“你怎么判断是偏移还是漂移？”答案是看误差随时间的走势，而不是看单次差值。</p>
  </section>
  <figure>
    <img src="../../assets/figures/clock-offset.svg" alt="偏移与漂移对比">
    <figcaption>同一张图里看“整体错开”和“越走越开”。</figcaption>
  </figure>
  <div data-tb-exercise="EX-SYNC-005"></div>
  <div data-tb-exercise="EX-SYNC-006"></div>
</article>
```

`content-packs/sample-sensors/modules/M01/lessons/L-SYNC-003.html`:

```html
<script type="application/json" id="tb-manifest">
{
  "schema": "tb/1",
  "id": "L-SYNC-003",
  "title": "设计一个同步误差测试",
  "module": "M01",
  "concepts": ["sensor-time-sync"],
  "target_level": "L3",
  "minutes": 25,
  "objectives": ["能设计可复现的同步误差测试", "能定义指标、阈值和失败模式"],
  "prerequisites": ["timestamp-basics", "clock-drift"],
  "exercises": ["EX-SYNC-002", "EX-SYNC-004"],
  "resources": ["DOC-ROS2-BAG", "DOC-PTP"]
}
</script>
<article class="tb-lesson">
  <h1>设计一个同步误差测试</h1>
  <section>
    <p>一个好的同步测试必须能回答三个问题：用什么事件做基准？用什么指标判定？失败时怎么定位？</p>
    <ol>
      <li>选一个两路传感器都能观测到的物理事件。</li>
      <li>采集带时间戳的数据，记录时钟源与打点位置。</li>
      <li>统计时间戳差的均值、方差和随时间的变化趋势。</li>
      <li>定义阈值，并记录一次失败案例用于复盘。</li>
    </ol>
  </section>
  <pre data-tb-block="code" data-language="bash"><code>ros2 bag record /camera/image_raw /imu/data --output sync-test
ros2 bag info sync-test</code></pre>
  <div data-tb-exercise="EX-SYNC-002"></div>
  <div data-tb-exercise="EX-SYNC-004"></div>
</article>
```

- [ ] **Step 6: Write the two SVG assets**

`content-packs/sample-sensors/assets/figures/clock-offset.svg`:

```svg
<svg viewBox="0 0 400 120" xmlns="http://www.w3.org/2000/svg">
  <line x1="20" y1="60" x2="380" y2="60" stroke="#d1d5db"/>
  <path d="M20,45 Q60,15 100,45 T180,45 T260,45 T340,45" fill="none" stroke="#2563eb" stroke-width="2"/>
  <path d="M20,75 Q60,45 100,75 T180,75 T260,75 T340,75" fill="none" stroke="#dc2626" stroke-width="2"/>
  <text x="20" y="105" fill="#6b7280" font-size="12">蓝色：传感器 A；红色：传感器 B；两条时间轴整体错开</text>
</svg>
```

`content-packs/sample-sensors/assets/widgets/sync-offset.svg`:

```svg
<svg viewBox="0 0 400 120" xmlns="http://www.w3.org/2000/svg">
  <line x1="0" y1="60" x2="400" y2="60" stroke="#d1d5db"/>
  <path d="M0,45 Q40,15 80,45 T160,45 T240,45 T320,45 T400,45" fill="none" stroke="#2563eb" stroke-width="2"/>
  <g transform="translate({{offset}}, 60) scale(1, {{drift}}) translate(0, -60)">
    <path d="M0,45 Q40,15 80,45 T160,45 T240,45 T320,45 T400,45" fill="none" stroke="#dc2626" stroke-width="2"/>
  </g>
  <text x="10" y="110" fill="#6b7280" font-size="12">offset={{offset}}ms · drift={{drift}}x</text>
</svg>
```

- [ ] **Step 7: Run tests and commit**

```bash
python -m pytest tests/test_sample_pack.py -q
python -m testbridge.cli validate content-packs/sample-sensors
git add content-packs tests/test_sample_pack.py
git commit -m "feat: add sample sensor time sync pack"
```

Expected: tests pass; CLI prints `0 error(s)`.

---

## Task 13: End-to-End Verification and Docs

**Files:**
- Create: `tests/test_e2e.py`
- Modify: `README.md`
- Modify: `docs/ROADMAP.md`

**Interfaces:**
- Produces: a verified P1 and updated docs.

- [ ] **Step 1: Write the end-to-end test**

```python
from pathlib import Path

from testbridge.build import build_pack
from testbridge.contract.validator import validate_pack
from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.exercise.grading import grade
from testbridge.lesson.renderer import render_lesson

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"


def sample_response(exercise):
    if exercise.type == "single_choice":
        return exercise.answer
    if exercise.type == "multi_choice":
        return exercise.answer
    if exercise.type == "short_answer":
        return exercise.answer.accepted[0]
    if exercise.type == "self_assess":
        return {"checked": [exercise.rubric[0].dimension]}
    return {"path": "data/artifacts/run.log", "checked": [exercise.rubric[0].dimension]}


def test_every_exercise_grades() -> None:
    pack = load_pack(SAMPLE)
    for exercise in pack.exercises.values():
        result = grade(exercise, sample_response(exercise))
        assert result.outcome in {"correct", "incorrect", "partial", "submitted"}


def test_every_lesson_renders_and_builds(tmp_path: Path) -> None:
    pack = load_pack(SAMPLE)
    assert validate_pack(SAMPLE).ok
    for lesson in pack.lessons_in_order():
        view = render_lesson(pack, lesson.manifest.id)
        assert "form class=\"tb-exercise\"" in view.body_html
    paths = build_pack(SAMPLE, tmp_path)
    assert len(paths) == 3
    assert all(path.is_file() for path in paths)


def test_evidence_round_trip(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "e.db")
    store.append(new_event(kind="exercise_attempt", concept_ids=["sensor-time-sync"]))
    path = tmp_path / "e.jsonl"
    assert store.export_jsonl(path) == 1
    assert store.import_jsonl(path) == 0
```

- [ ] **Step 2: Run the full test suite**

```bash
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Validate and build the sample pack**

```bash
python -m testbridge.cli validate content-packs/sample-sensors
python -m testbridge.cli build content-packs/sample-sensors --out dist
find dist -type f | sort
```

Expected: `0 error(s)`; three HTML files under `dist/sample-sensors/modules/M01/lessons/`.

- [ ] **Step 4: Smoke-test the web app**

```bash
python -m testbridge.cli serve content-packs/sample-sensors --port 8000
```

Open `http://127.0.0.1:8000`, complete one exercise, then open `/progress`. Stop the server with Ctrl-C.

- [ ] **Step 5: Update README quick start**

Replace the “快速开始” section with:

````markdown
## 快速开始

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e ".[dev]"

# 校验内容包
python -m testbridge.cli validate content-packs/sample-sensors

# 构建可离线打开的单文件课程
python -m testbridge.cli build content-packs/sample-sensors --out dist

# 启动学习界面
python -m testbridge.cli serve content-packs/sample-sensors --port 8000
```

打开 http://127.0.0.1:8000 。
````

- [ ] **Step 6: Update ROADMAP status**

Change the top block to:

```markdown
> **当前期：P1（内容契约 + 运行时）**
> 状态：实现完成，待验收
```

- [ ] **Step 7: Commit**

```bash
git add tests/test_e2e.py README.md docs/ROADMAP.md
git commit -m "test: verify P1 end to end and update docs"
```

---

## Self-Review Checklist

- [ ] Every `tb/1` model in the spec has a Pydantic model in Task 1.
- [ ] Every validation rule in spec §5.8 is covered in Task 4.
- [ ] Every P1 exercise type in spec §5.4 is graded in Task 6 and rendered in Task 8.
- [ ] Evidence is append-only and exportable in Task 7.
- [ ] Lesson rendering and navigation are covered in Task 8.
- [ ] Web routes and evidence submission are covered in Task 9.
- [ ] Exercise runtime, hints, and widgets are covered in Task 10.
- [ ] CLI validate/build/serve and evidence export/import are covered in Task 11.
- [ ] Sample pack exercises every P1 feature in Task 12.
- [ ] End-to-end test and docs update are covered in Task 13.
- [ ] No task implements mastery, FSRS, recommendations, AI generation, interview, or company intel.
- [ ] No engine module contains domain text; all domain text lives under `content-packs/`.
