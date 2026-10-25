# P2 Learning Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn appended evidence into a learning loop: rule + BKT mastery, FSRS exercise reviews, readiness, a deterministic daily planner, dashboard pages, CLI commands, and a rebuildable derived state.

**Architecture:** A `LearningService` aggregates `EvidenceStore`, `LearningStore`, mastery estimation, FSRS scheduling, readiness, and planning. Evidence stays the source of truth; `mastery_state` / `review_state` are rebuildable caches; `goal` is learner configuration.

**Tech Stack:** Python 3.10+, Pydantic v2, FastAPI, Jinja2, SQLite, `fsrs==6.3.x`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-25-p2-learning-loop-design.md`

## Global Constraints

- Evidence is append-only and remains the single source of truth; `mastery_state` / `review_state` are derived and rebuildable.
- Grading and scheduling are deterministic in P2; no LLM calls.
- Engine modules never contain domain text; all subject content stays under `content-packs/`.
- P2 must not implement AI generation, interview, company intel, or multi-user permissions.
- Use `fsrs>=6.3,<7` (PyPI package `fsrs`), `Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False)`.
- All timestamps are UTC ISO 8601; every algorithm accepts an injectable `now`.
- Every task ends with a passing test run and a commit.
- Keep the P1 118-test suite green.

---

## Task 0: P1 Carry-Forwards

**Files:**
- Modify: `web/app.py`
- Modify: `web/templates/lesson.html`
- Modify: `web/static/tb-runtime.js`
- Test: `tests/test_web.py`

**Interfaces:**
- Produces: lesson pages no longer embed exercise answer data; `POST /api/evidence` rejects an exercise that is not in the requested lesson.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web.py`:

```python
SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"


def test_lesson_page_does_not_embed_exercise_data(tmp_path: Path) -> None:
    c = TestClient(create_app(FIXTURE, tmp_path / "test.db"))
    response = c.get("/lesson/L-ONE")
    assert response.status_code == 200
    assert "tb-exercise-data" not in response.text
    assert '"answer"' not in response.text


def test_cross_lesson_exercise_is_rejected(tmp_path: Path) -> None:
    c = TestClient(create_app(SAMPLE, tmp_path / "test.db"))
    response = c.post(
        "/api/evidence",
        json={"lesson_id": "L-SYNC-001", "exercise_id": "EX-SYNC-005", "response": "a"},
    )
    assert response.status_code == 400
    assert "exercise not in lesson" in response.text
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_web.py -q
```

Expected: the first test fails because `tb-exercise-data` is still present; the second returns 200 instead of 400.

Before running the tests, delete the now-obsolete `test_exercise_data_escapes_script_close` from `tests/test_web.py`; it exercises the data block being removed. In `test_runtime_script_is_served`, remove the `JSON.parse` assertion; the runtime no longer parses exercise data. Keep the `/api/evidence`, `tb-widget-template`, no-`eval`, and no-`new Function` assertions.

- [ ] **Step 3: Remove the embedded exercise data**

In `web/app.py`, the lesson route currently computes `exercise_data` and passes it to the template. Remove that computation and the `exercise_data=` context argument. In `web/templates/lesson.html`, delete:

```html
<script id="tb-exercise-data" type="application/json">{{ exercise_data | safe }}</script>
```

In `web/static/tb-runtime.js`, delete:

```javascript
const dataEl = document.getElementById("tb-exercise-data");
const exercises = dataEl ? JSON.parse(dataEl.textContent) : {};
```

The forms are already server-rendered; the runtime does not need exercise data.

Also remove the now-unused `_script_json` helper and `import json` from `web/app.py`; the only remaining consumer is the standalone build, which has its own helper.

- [ ] **Step 4: Add the exercise-belongs-to-lesson check**

In `web/app.py`, inside `submit_evidence`, after resolving `lesson` and before grading:

```python
    lesson = pack.lessons.get(payload.lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="lesson not found")
    if payload.exercise_id not in lesson.manifest.exercises:
        raise HTTPException(status_code=400, detail="exercise not in lesson")
    exercise = pack.exercises.get(payload.exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="exercise not found")
```

Keep the existing 404 behavior for unknown lessons/exercises.

- [ ] **Step 5: Run the tests and commit**

```bash
.venv/Scripts/python -m pytest tests/test_web.py -q
git add web/app.py web/templates/lesson.html web/static/tb-runtime.js tests/test_web.py
git commit -m "fix: hide exercise answers and validate lesson ownership"
```

Expected: all web tests pass.

---

## Task 1: Learning Store, Time Utilities, and Goal

**Files:**
- Create: `src/testbridge/learning/__init__.py`
- Create: `src/testbridge/learning/timeutil.py`
- Create: `src/testbridge/learning/store.py`
- Test: `tests/test_learning_store.py`

**Interfaces:**
- Produces: `Goal`, `MasteryState`, `ReviewState`, `LearningStore`, `utcnow`, `parse_iso`, `iso`.
- `LearningStore` methods: `get_goal`, `set_goal`, `get_mastery`, `upsert_mastery`, `list_mastery`, `clear_mastery`, `get_review`, `upsert_review`, `list_reviews`, `due_reviews`, `clear_reviews`, `replace_all`.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timezone
from pathlib import Path

from testbridge.learning.store import Goal, LearningStore, MasteryState, ReviewState


def state(concept_id: str = "c-one") -> MasteryState:
    return MasteryState(
        learner_id="local", concept_id=concept_id, rule_score=0.5, bkt_p=0.4,
        exercise_observations=2, other_observations=1, estimate=0.5,
        confidence=0.5, level="L2", updated_at="2026-10-25T00:00:00+00:00",
    )


def review(exercise_id: str = "EX-ONE", due: str = "2026-10-25T00:00:00+00:00") -> ReviewState:
    return ReviewState(
        learner_id="local", exercise_id=exercise_id, concept_ids=["c-one"],
        due=due, stability=1.0, difficulty=5.0, reps=1, lapses=0,
        state="Review", last_review="2026-10-24T00:00:00+00:00",
        card_json={"card_id": 1, "state": 2, "step": 0, "stability": 1.0,
                   "difficulty": 5.0, "due": due, "last_review": "2026-10-24T00:00:00+00:00"},
    )


def test_goal_defaults_and_round_trip(tmp_path: Path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    assert store.get_goal("local").daily_minutes == 45
    store.set_goal(Goal(learner_id="local", target_role="测试开发", daily_minutes=60,
                        concept_overrides={"c-one": 1.5}))
    goal = store.get_goal("local")
    assert goal.daily_minutes == 60
    assert goal.concept_overrides == {"c-one": 1.5}


def test_mastery_upsert_and_list(tmp_path: Path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    store.upsert_mastery(state())
    assert store.get_mastery("local", "c-one").estimate == 0.5
    assert set(store.list_mastery("local")) == {"c-one"}


def test_review_upsert_and_due_filter(tmp_path: Path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    store.upsert_review(review("EX-ONE", "2026-10-24T00:00:00+00:00"))
    store.upsert_review(review("EX-TWO", "2026-10-26T00:00:00+00:00"))
    due = store.due_reviews("local", datetime(2026, 10, 25, tzinfo=timezone.utc))
    assert [item.exercise_id for item in due] == ["EX-ONE"]
    assert store.get_review("local", "EX-ONE").concept_ids == ["c-one"]


def test_replace_all_and_clear(tmp_path: Path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    store.upsert_mastery(state("c-old"))
    store.replace_all("local", {"c-one": state()}, {"EX-ONE": review()})
    assert set(store.list_mastery("local")) == {"c-one"}
    assert set(store.list_reviews("local")) == {"EX-ONE"}
    store.clear_mastery("local")
    store.clear_reviews("local")
    assert store.list_mastery("local") == {}
    assert store.list_reviews("local") == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_learning_store.py -q
```

Expected: import error for `testbridge.learning.store`.

- [ ] **Step 3: Implement `timeutil.py`**

```python
"""UTC time helpers shared by the P2 learning loop."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()
```

- [ ] **Step 4: Implement `store.py`**

```python
"""SQLite storage for derived learning state and the learner goal."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .timeutil import iso

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mastery_state (
  learner_id TEXT NOT NULL,
  concept_id TEXT NOT NULL,
  rule_score REAL NOT NULL,
  bkt_p REAL NOT NULL,
  exercise_observations INTEGER NOT NULL,
  other_observations INTEGER NOT NULL,
  estimate REAL NOT NULL,
  confidence REAL NOT NULL,
  level TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (learner_id, concept_id)
);

CREATE TABLE IF NOT EXISTS review_state (
  learner_id TEXT NOT NULL,
  exercise_id TEXT NOT NULL,
  concept_ids TEXT NOT NULL,
  due TEXT NOT NULL,
  stability REAL NOT NULL,
  difficulty REAL NOT NULL,
  reps INTEGER NOT NULL,
  lapses INTEGER NOT NULL,
  state TEXT NOT NULL,
  last_review TEXT,
  card_json TEXT NOT NULL,
  PRIMARY KEY (learner_id, exercise_id)
);

CREATE TABLE IF NOT EXISTS goal (
  learner_id TEXT PRIMARY KEY,
  target_role TEXT NOT NULL DEFAULT '',
  weekly_hours REAL NOT NULL DEFAULT 0,
  daily_minutes INTEGER NOT NULL DEFAULT 45,
  concept_overrides_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Goal:
    learner_id: str = "local"
    target_role: str = ""
    weekly_hours: float = 0.0
    daily_minutes: int = 45
    concept_overrides: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class MasteryState:
    learner_id: str
    concept_id: str
    rule_score: float
    bkt_p: float
    exercise_observations: int
    other_observations: int
    estimate: float
    confidence: float
    level: str
    updated_at: str


@dataclass(frozen=True)
class ReviewState:
    learner_id: str
    exercise_id: str
    concept_ids: list[str]
    due: str
    stability: float
    difficulty: float
    reps: int
    lapses: int
    state: str
    last_review: str | None
    card_json: dict[str, Any]


class LearningStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA_SQL)

    def get_goal(self, learner_id: str = "local") -> Goal:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM goal WHERE learner_id = ?", (learner_id,)).fetchone()
        if row is None:
            return Goal(learner_id=learner_id)
        return Goal(
            learner_id=row["learner_id"],
            target_role=row["target_role"],
            weekly_hours=row["weekly_hours"],
            daily_minutes=row["daily_minutes"],
            concept_overrides=json.loads(row["concept_overrides_json"]),
        )

    def set_goal(self, goal: Goal) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO goal
                (learner_id, target_role, weekly_hours, daily_minutes,
                 concept_overrides_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(learner_id) DO UPDATE SET
                  target_role=excluded.target_role,
                  weekly_hours=excluded.weekly_hours,
                  daily_minutes=excluded.daily_minutes,
                  concept_overrides_json=excluded.concept_overrides_json,
                  updated_at=excluded.updated_at
                """,
                (
                    goal.learner_id, goal.target_role, goal.weekly_hours,
                    goal.daily_minutes,
                    json.dumps(goal.concept_overrides, ensure_ascii=False),
                    iso(datetime.now().astimezone()),
                ),
            )

    def get_mastery(self, learner_id: str, concept_id: str) -> MasteryState | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM mastery_state WHERE learner_id = ? AND concept_id = ?",
                (learner_id, concept_id),
            ).fetchone()
        return self._row_to_mastery(row) if row else None

    def upsert_mastery(self, state: MasteryState) -> None:
        with sqlite3.connect(self.path) as conn:
            self._insert_mastery(conn, state)

    def list_mastery(self, learner_id: str) -> dict[str, MasteryState]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM mastery_state WHERE learner_id = ?", (learner_id,)
            ).fetchall()
        return {row["concept_id"]: self._row_to_mastery(row) for row in rows}

    def clear_mastery(self, learner_id: str) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM mastery_state WHERE learner_id = ?", (learner_id,))

    def get_review(self, learner_id: str, exercise_id: str) -> ReviewState | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM review_state WHERE learner_id = ? AND exercise_id = ?",
                (learner_id, exercise_id),
            ).fetchone()
        return self._row_to_review(row) if row else None

    def upsert_review(self, state: ReviewState) -> None:
        with sqlite3.connect(self.path) as conn:
            self._insert_review(conn, state)

    def list_reviews(self, learner_id: str) -> dict[str, ReviewState]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM review_state WHERE learner_id = ?", (learner_id,)
            ).fetchall()
        return {row["exercise_id"]: self._row_to_review(row) for row in rows}

    def due_reviews(self, learner_id: str, now: datetime) -> list[ReviewState]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM review_state
                WHERE learner_id = ? AND due <= ?
                ORDER BY due, exercise_id
                """,
                (learner_id, iso(now)),
            ).fetchall()
        return [self._row_to_review(row) for row in rows]

    def clear_reviews(self, learner_id: str) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM review_state WHERE learner_id = ?", (learner_id,))

    def replace_all(
        self,
        learner_id: str,
        mastery: dict[str, MasteryState],
        reviews: dict[str, ReviewState],
    ) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM mastery_state WHERE learner_id = ?", (learner_id,))
            conn.execute("DELETE FROM review_state WHERE learner_id = ?", (learner_id,))
            for state in mastery.values():
                self._insert_mastery(conn, state)
            for review in reviews.values():
                self._insert_review(conn, review)

    @staticmethod
    def _insert_mastery(conn: sqlite3.Connection, state: MasteryState) -> None:
        conn.execute(
            """
            INSERT INTO mastery_state
            (learner_id, concept_id, rule_score, bkt_p, exercise_observations,
             other_observations, estimate, confidence, level, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(learner_id, concept_id) DO UPDATE SET
              rule_score=excluded.rule_score,
              bkt_p=excluded.bkt_p,
              exercise_observations=excluded.exercise_observations,
              other_observations=excluded.other_observations,
              estimate=excluded.estimate,
              confidence=excluded.confidence,
              level=excluded.level,
              updated_at=excluded.updated_at
            """,
            (
                state.learner_id, state.concept_id, state.rule_score, state.bkt_p,
                state.exercise_observations, state.other_observations,
                state.estimate, state.confidence, state.level, state.updated_at,
            ),
        )

    @staticmethod
    def _insert_review(conn: sqlite3.Connection, review: ReviewState) -> None:
        conn.execute(
            """
            INSERT INTO review_state
            (learner_id, exercise_id, concept_ids, due, stability, difficulty,
             reps, lapses, state, last_review, card_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(learner_id, exercise_id) DO UPDATE SET
              concept_ids=excluded.concept_ids,
              due=excluded.due,
              stability=excluded.stability,
              difficulty=excluded.difficulty,
              reps=excluded.reps,
              lapses=excluded.lapses,
              state=excluded.state,
              last_review=excluded.last_review,
              card_json=excluded.card_json
            """,
            (
                review.learner_id, review.exercise_id,
                json.dumps(review.concept_ids, ensure_ascii=False),
                review.due, review.stability, review.difficulty,
                review.reps, review.lapses, review.state, review.last_review,
                json.dumps(review.card_json, ensure_ascii=False),
            ),
        )

    @staticmethod
    def _row_to_mastery(row: sqlite3.Row) -> MasteryState:
        return MasteryState(
            learner_id=row["learner_id"], concept_id=row["concept_id"],
            rule_score=row["rule_score"], bkt_p=row["bkt_p"],
            exercise_observations=row["exercise_observations"],
            other_observations=row["other_observations"],
            estimate=row["estimate"], confidence=row["confidence"],
            level=row["level"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_review(row: sqlite3.Row) -> ReviewState:
        return ReviewState(
            learner_id=row["learner_id"], exercise_id=row["exercise_id"],
            concept_ids=json.loads(row["concept_ids"]), due=row["due"],
            stability=row["stability"], difficulty=row["difficulty"],
            reps=row["reps"], lapses=row["lapses"], state=row["state"],
            last_review=row["last_review"], card_json=json.loads(row["card_json"]),
        )
```

- [ ] **Step 5: Run the tests and commit**

```bash
.venv/Scripts/python -m pytest tests/test_learning_store.py -q
git add src/testbridge/learning tests/test_learning_store.py
git commit -m "feat: add learning state store and goal"
```

Expected: 4 tests pass.

---

## Task 2: Rule-Based Mastery

**Files:**
- Create: `src/testbridge/mastery/__init__.py`
- Create: `src/testbridge/mastery/rule.py`
- Test: `tests/test_rule_mastery.py`

**Interfaces:**
- Produces: `RuleResult`, `event_score(event)`, `rule_score(events, concept_id, now)`, `level_for(estimate)`, `confidence_for(exercise_obs, other_obs)`.
- `RuleResult` fields: `score`, `exercise_observations`, `other_observations`, `weight_sum`.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timedelta, timezone

from testbridge.evidence.store import new_event
from testbridge.mastery.rule import confidence_for, level_for, rule_score

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def event(kind: str, outcome: str, concepts: list[str], days_ago: float = 0) -> object:
    item = new_event(kind=kind, concept_ids=concepts, outcome=outcome, score=1.0 if outcome == "correct" else 0.0, max_score=1.0)
    return item.__class__(**{**item.__dict__, "created_at": (NOW - timedelta(days=days_ago)).isoformat()})


def test_no_evidence_is_zero() -> None:
    result = rule_score([], "c-one", NOW)
    assert result.score == 0.0
    assert result.exercise_observations == 0


def test_single_correct_exercise() -> None:
    result = rule_score([event("exercise_attempt", "correct", ["c-one"])], "c-one", NOW)
    assert result.score == 1.0
    assert result.exercise_observations == 1


def test_recent_evidence_outweighs_old() -> None:
    old = event("exercise_attempt", "correct", ["c-one"], days_ago=60)
    recent = event("exercise_attempt", "incorrect", ["c-one"], days_ago=0)
    result = rule_score([old, recent], "c-one", NOW)
    assert 0.0 < result.score < 0.5


def test_self_assess_has_lower_weight() -> None:
    exercise = event("exercise_attempt", "incorrect", ["c-one"])
    self_assess = event("self_assess", "submitted", ["c-one"])
    result = rule_score([exercise, self_assess], "c-one", NOW)
    assert result.other_observations == 1
    assert result.score < 0.5


def test_multi_concept_event_is_shared() -> None:
    shared = event("exercise_attempt", "correct", ["c-one", "c-two"])
    solo = event("exercise_attempt", "incorrect", ["c-one"])
    result = rule_score([shared, solo], "c-one", NOW)
    assert result.score < 1.0


def test_levels_and_confidence() -> None:
    assert level_for(0.1) == "L0"
    assert level_for(0.3) == "L1"
    assert level_for(0.6) == "L2"
    assert level_for(0.8) == "L3"
    assert level_for(0.95) == "L4"
    assert confidence_for(0, 0) == 0.0
    assert confidence_for(5, 0) == 1.0
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_rule_mastery.py -q
```

Expected: import error.

- [ ] **Step 3: Implement `rule.py`**

```python
"""Rule-based, explainable mastery from evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from testbridge.evidence.store import EvidenceEvent
from testbridge.learning.timeutil import parse_iso

KIND_WEIGHTS = {"exercise_attempt": 1.0, "self_assess": 0.5, "artifact": 0.7}
HALF_LIFE_DAYS = 30.0
LEVEL_THRESHOLDS = ((0.90, "L4"), (0.75, "L3"), (0.50, "L2"), (0.25, "L1"))


@dataclass(frozen=True)
class RuleResult:
    score: float
    exercise_observations: int
    other_observations: int
    weight_sum: float


def event_score(event: EvidenceEvent) -> float:
    if event.score is not None and event.max_score:
        return max(0.0, min(1.0, event.score / event.max_score))
    return {"correct": 1.0, "partial": 0.5, "incorrect": 0.0, "submitted": 0.5}.get(
        event.outcome or "", 0.5
    )


def rule_score(events: Iterable[EvidenceEvent], concept_id: str, now: datetime) -> RuleResult:
    numerator = 0.0
    denominator = 0.0
    exercise_observations = 0
    other_observations = 0
    for event in events:
        if concept_id not in event.concept_ids:
            continue
        kind_weight = KIND_WEIGHTS.get(event.kind)
        if kind_weight is None:
            continue
        if event.kind == "exercise_attempt":
            exercise_observations += 1
        else:
            other_observations += 1
        age_days = max(0.0, (now - parse_iso(event.created_at)).total_seconds() / 86400)
        decay = 0.5 ** (age_days / HALF_LIFE_DAYS)
        share = 1.0 / max(1, len(event.concept_ids))
        weight = kind_weight * decay * share
        numerator += weight * event_score(event)
        denominator += weight
    score = numerator / denominator if denominator else 0.0
    return RuleResult(score, exercise_observations, other_observations, denominator)


def level_for(estimate: float) -> str:
    for threshold, level in LEVEL_THRESHOLDS:
        if estimate >= threshold:
            return level
    return "L0"


def confidence_for(exercise_observations: int, other_observations: int) -> float:
    return min(1.0, (exercise_observations + 0.5 * other_observations) / 5.0)
```

- [ ] **Step 4: Run the tests and commit**

```bash
.venv/Scripts/python -m pytest tests/test_rule_mastery.py -q
git add src/testbridge/mastery tests/test_rule_mastery.py
git commit -m "feat: add rule-based mastery"
```

Expected: 6 tests pass.

---

## Task 3: Bayesian Knowledge Tracing

**Files:**
- Create: `src/testbridge/mastery/bkt.py`
- Test: `tests/test_bkt.py`

**Interfaces:**
- Produces: `BKTParams`, `BKTState`, `initial_state(params=None)`, `observe(state, correct, params=None)`, `replay(observations, params=None)`.

- [ ] **Step 1: Write the failing tests**

```python
from testbridge.mastery.bkt import BKTParams, initial_state, observe, replay


def test_initial_state() -> None:
    state = initial_state()
    assert state.p == 0.3
    assert state.observations == 0


def test_correct_increases_and_incorrect_decreases() -> None:
    start = initial_state()
    after_correct = observe(start, True)
    after_wrong = observe(start, False)
    assert after_correct.p > start.p
    assert after_wrong.p < start.p
    assert after_correct.observations == 1


def test_replay_is_deterministic() -> None:
    one = replay([True, True, False])
    two = replay([True, True, False])
    assert one == two
    assert one.observations == 3


def test_custom_params() -> None:
    params = BKTParams(p_init=0.5, p_learn=0.2, p_guess=0.1, p_slip=0.05)
    state = observe(initial_state(params), True, params)
    assert 0.0 <= state.p <= 1.0
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_bkt.py -q
```

Expected: import error.

- [ ] **Step 3: Implement `bkt.py`**

```python
"""Per-concept Bayesian Knowledge Tracing with fixed defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class BKTParams:
    p_init: float = 0.3
    p_learn: float = 0.15
    p_guess: float = 0.2
    p_slip: float = 0.1


@dataclass(frozen=True)
class BKTState:
    p: float
    observations: int


def initial_state(params: BKTParams | None = None) -> BKTState:
    params = params or BKTParams()
    return BKTState(p=params.p_init, observations=0)


def observe(state: BKTState, correct: bool, params: BKTParams | None = None) -> BKTState:
    params = params or BKTParams()
    p = state.p
    if correct:
        p_obs = p * (1 - params.p_slip) / (
            p * (1 - params.p_slip) + (1 - p) * params.p_guess
        )
    else:
        p_obs = p * params.p_slip / (p * params.p_slip + (1 - p) * (1 - params.p_guess))
    p_next = p_obs + (1 - p_obs) * params.p_learn
    return BKTState(p=max(0.0, min(1.0, p_next)), observations=state.observations + 1)


def replay(observations: Iterable[bool], params: BKTParams | None = None) -> BKTState:
    state = initial_state(params)
    for correct in observations:
        state = observe(state, correct, params)
    return state
```

- [ ] **Step 4: Run the tests and commit**

```bash
.venv/Scripts/python -m pytest tests/test_bkt.py -q
git add src/testbridge/mastery/bkt.py tests/test_bkt.py
git commit -m "feat: add BKT mastery estimator"
```

Expected: 4 tests pass.

---

## Task 4: Hybrid Mastery Estimator

**Files:**
- Create: `src/testbridge/mastery/estimator.py`
- Test: `tests/test_estimator.py`

**Interfaces:**
- Consumes: `rule_score`, `level_for`, `confidence_for`, `BKTState`, `initial_state`, `observe`.
- Produces: `HANDOFF_OBSERVATIONS = 3`, `MasteryView`, `replay_bkt(events, concept_id, params=None)`, `estimate(concept_id, events, now, bkt_state=None, params=None)`.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timezone

from testbridge.evidence.store import new_event
from testbridge.mastery.estimator import HANDOFF_OBSERVATIONS, estimate
from testbridge.mastery.bkt import initial_state

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def exercise(outcome: str) -> object:
    return new_event(
        kind="exercise_attempt", concept_ids=["c-one"], outcome=outcome,
        score=1.0 if outcome == "correct" else 0.0, max_score=1.0,
    )


def test_uses_rule_before_handoff() -> None:
    events = [exercise("correct"), exercise("incorrect")]
    view = estimate("c-one", events, NOW)
    assert view.exercise_observations == 2
    assert view.estimate == view.rule_score


def test_uses_bkt_after_handoff() -> None:
    events = [exercise("correct") for _ in range(HANDOFF_OBSERVATIONS)]
    view = estimate("c-one", events, NOW)
    assert view.exercise_observations == 3
    assert view.estimate == view.bkt_p
    assert view.estimate != view.rule_score


def test_confidence_and_level() -> None:
    events = [exercise("correct") for _ in range(5)]
    view = estimate("c-one", events, NOW)
    assert view.confidence == 1.0
    assert view.level in {"L1", "L2", "L3", "L4"}


def test_explicit_bkt_state_is_used() -> None:
    state = initial_state()
    view = estimate("c-one", [], NOW, bkt_state=state)
    assert view.bkt_p == state.p
    assert view.estimate == 0.0  # rule score, because observations < 3
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_estimator.py -q
```

Expected: import error.

- [ ] **Step 3: Implement `estimator.py`**

```python
"""Combine rule-based mastery and BKT with a cold-start handoff."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from testbridge.evidence.store import EvidenceEvent
from testbridge.mastery.bkt import BKTParams, BKTState, initial_state, observe
from testbridge.mastery.rule import confidence_for, level_for, rule_score

HANDOFF_OBSERVATIONS = 3


@dataclass(frozen=True)
class MasteryView:
    concept_id: str
    rule_score: float
    bkt_p: float
    estimate: float
    confidence: float
    level: str
    exercise_observations: int
    other_observations: int


def replay_bkt(
    events: Iterable[EvidenceEvent],
    concept_id: str,
    params: BKTParams | None = None,
) -> BKTState:
    state = initial_state(params)
    ordered = sorted(events, key=lambda event: (event.created_at, event.id))
    for event in ordered:
        if event.kind != "exercise_attempt" or concept_id not in event.concept_ids:
            continue
        state = observe(state, event.outcome == "correct", params)
    return state


def estimate(
    concept_id: str,
    events: Iterable[EvidenceEvent],
    now: datetime,
    bkt_state: BKTState | None = None,
    params: BKTParams | None = None,
) -> MasteryView:
    events = list(events)
    rule = rule_score(events, concept_id, now)
    state = bkt_state or replay_bkt(events, concept_id, params)
    estimate_value = state.p if state.observations >= HANDOFF_OBSERVATIONS else rule.score
    return MasteryView(
        concept_id=concept_id,
        rule_score=rule.score,
        bkt_p=state.p,
        estimate=estimate_value,
        confidence=confidence_for(rule.exercise_observations, rule.other_observations),
        level=level_for(estimate_value),
        exercise_observations=rule.exercise_observations,
        other_observations=rule.other_observations,
    )
```

- [ ] **Step 4: Run the tests and commit**

```bash
.venv/Scripts/python -m pytest tests/test_estimator.py -q
git add src/testbridge/mastery/estimator.py tests/test_estimator.py
git commit -m "feat: combine rule and BKT mastery"
```

Expected: 4 tests pass.

---

## Task 5: FSRS Review Scheduler

**Files:**
- Modify: `pyproject.toml` (add `fsrs>=6.3,<7`)
- Create: `src/testbridge/schedule/__init__.py`
- Create: `src/testbridge/schedule/fsrs.py`
- Test: `tests/test_fsrs.py`

**Interfaces:**
- Consumes: `EvidenceEvent`, `ReviewState`, `parse_iso`, `iso`.
- Produces: `rating_for(event)`, `review_event(exercise_id, concept_ids, event, previous=None, learner_id="local")`, `SCHEDULER`.

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add to `dependencies`:

```toml
    "fsrs>=6.3,<7",
```

Then run:

```bash
.venv/Scripts/python -m pip install -q "fsrs>=6.3,<7"
```

- [ ] **Step 2: Write the failing tests**

```python
from datetime import datetime, timezone

from fsrs import Rating
from testbridge.evidence.store import new_event
from testbridge.schedule.fsrs import rating_for, review_event

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def attempt(outcome: str, hints: int = 0, duration: int = 0) -> object:
    return new_event(
        kind="exercise_attempt", concept_ids=["c-one"], outcome=outcome,
        score=1.0 if outcome == "correct" else 0.0, max_score=1.0,
        payload={"hints_used": hints, "duration_ms": duration},
    )


def test_rating_mapping() -> None:
    assert rating_for(attempt("incorrect")) == Rating.Again
    assert rating_for(attempt("partial")) == Rating.Hard
    assert rating_for(attempt("correct", hints=1)) == Rating.Hard
    assert rating_for(attempt("correct", duration=10_000)) == Rating.Easy
    assert rating_for(attempt("correct", duration=60_000)) == Rating.Good


def test_review_creates_card() -> None:
    state = review_event("EX-ONE", ["c-one"], attempt("correct"))
    assert state.exercise_id == "EX-ONE"
    assert state.reps == 1
    assert state.state == "Review"
    assert state.due
    assert state.card_json["due"] == state.due


def test_review_updates_existing_card() -> None:
    first = review_event("EX-ONE", ["c-one"], attempt("correct"))
    second = review_event("EX-ONE", ["c-one"], attempt("incorrect"), previous=first)
    assert second.reps == 2
    assert second.lapses == 1
    assert second.state in {"Review", "Relearning"}
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_fsrs.py -q
```

Expected: import error for `testbridge.schedule.fsrs`.

- [ ] **Step 4: Implement `fsrs.py`**

```python
"""Exercise-level FSRS scheduling with automatic ratings."""

from __future__ import annotations

from fsrs import Card, Rating, Scheduler

from testbridge.evidence.store import EvidenceEvent
from testbridge.learning.store import ReviewState
from testbridge.learning.timeutil import iso, parse_iso

SCHEDULER = Scheduler(
    learning_steps=(),
    relearning_steps=(),
    enable_fuzzing=False,
)


def rating_for(event: EvidenceEvent) -> Rating:
    if event.outcome == "incorrect":
        return Rating.Again
    if event.outcome == "partial":
        return Rating.Hard
    payload = event.payload or {}
    hints = int(payload.get("hints_used", 0) or 0)
    duration = int(payload.get("duration_ms", 0) or 0)
    if event.outcome == "correct":
        if hints > 0:
            return Rating.Hard
        if 0 < duration <= 20_000:
            return Rating.Easy
        return Rating.Good
    return Rating.Good


def review_event(
    exercise_id: str,
    concept_ids: list[str],
    event: EvidenceEvent,
    previous: ReviewState | None = None,
    learner_id: str = "local",
) -> ReviewState:
    card = Card.from_dict(previous.card_json) if previous else Card()
    rating = rating_for(event)
    reps = (previous.reps if previous else 0) + 1
    lapses = previous.lapses if previous else 0
    if previous and rating == Rating.Again and previous.state in {"Review", "Relearning"}:
        lapses += 1
    card, _ = SCHEDULER.review_card(
        card, rating, review_datetime=parse_iso(event.created_at)
    )
    return ReviewState(
        learner_id=learner_id,
        exercise_id=exercise_id,
        concept_ids=list(concept_ids),
        due=iso(card.due),
        stability=card.stability or 0.0,
        difficulty=card.difficulty or 0.0,
        reps=reps,
        lapses=lapses,
        state=card.state.name,
        last_review=iso(card.last_review) if card.last_review else None,
        card_json=card.to_dict(),
    )
```

- [ ] **Step 5: Run the tests and commit**

```bash
.venv/Scripts/python -m pytest tests/test_fsrs.py -q
git add pyproject.toml src/testbridge/schedule tests/test_fsrs.py
git commit -m "feat: add FSRS exercise scheduling"
```

Expected: 3 tests pass.

---

## Task 6: Learning Service

**Files:**
- Create: `src/testbridge/learning/service.py`
- Create: `src/testbridge/recommend/__init__.py`
- Create: `src/testbridge/recommend/planner.py` (temporary stub, replaced in Task 9)
- Create: `src/testbridge/readiness.py` (temporary stub, replaced in Task 8)
- Test: `tests/test_learning_service.py`

**Interfaces:**
- Consumes: `ContentPack`, `EvidenceStore`, `LearningStore`, `estimate`, `BKTState`, `initial_state`, `observe`, `review_event`, `rule_score`, `level_for`, `confidence_for`, `HANDOFF_OBSERVATIONS`.
- Produces: `LearningService` with `now`, `goal`, `mastery`, `all_mastery`, `record`, `due_reviews`.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timezone
from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.learning.service import LearningService
from testbridge.learning.store import LearningStore

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def service(tmp_path: Path) -> LearningService:
    pack = load_pack(SAMPLE)
    return LearningService(
        pack, EvidenceStore(tmp_path / "e.db"), LearningStore(tmp_path / "l.db"),
        now_fn=lambda: NOW,
    )


def event(outcome: str) -> object:
    return new_event(
        kind="exercise_attempt", lesson_id="L-SYNC-001", exercise_id="EX-SYNC-001",
        concept_ids=["sensor-time-sync"], outcome=outcome,
        score=1.0 if outcome == "correct" else 0.0, max_score=1.0,
    )


def test_record_updates_mastery_and_review(tmp_path: Path) -> None:
    svc = service(tmp_path)
    item = event("correct")
    svc.evidence.append(item)
    svc.record(item)
    view = svc.mastery("sensor-time-sync")
    assert view.exercise_observations == 1
    assert view.estimate > 0
    assert svc.store.get_review("local", "EX-SYNC-001") is not None


def test_handoff_after_three_exercises(tmp_path: Path) -> None:
    svc = service(tmp_path)
    for _ in range(3):
        item = event("correct")
        svc.evidence.append(item)
        svc.record(item)
    view = svc.mastery("sensor-time-sync")
    assert view.exercise_observations == 3
    assert view.estimate == view.bkt_p


def test_self_assess_updates_rule_not_review(tmp_path: Path) -> None:
    svc = service(tmp_path)
    item = new_event(
        kind="self_assess", concept_ids=["sensor-time-sync"], outcome="submitted",
        score=0.5, max_score=1.0,
    )
    svc.evidence.append(item)
    svc.record(item)
    view = svc.mastery("sensor-time-sync")
    assert view.other_observations == 1
    assert svc.store.list_reviews("local") == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_learning_service.py -q
```

Expected: import error.

- [ ] **Step 3: Implement `service.py`**

```python
"""Aggregate evidence, mastery, review scheduling, readiness, and planning."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from testbridge.content.repository import ContentPack
from testbridge.evidence.store import EvidenceEvent, EvidenceStore
from testbridge.learning.store import Goal, LearningStore, MasteryState
from testbridge.learning.timeutil import iso, utcnow
from testbridge.mastery.bkt import BKTState, initial_state, observe
from testbridge.mastery.estimator import HANDOFF_OBSERVATIONS, MasteryView, estimate
from testbridge.mastery.rule import confidence_for, level_for, rule_score
from testbridge.readiness import ReadinessView, calculate_readiness
from testbridge.recommend.planner import DailyPlan, Planner
from testbridge.schedule.fsrs import review_event


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

    def mastery(self, concept_id: str) -> MasteryView:
        events = self.evidence.list(concept_id=concept_id, limit=1_000_000)
        state = self.store.get_mastery(self.learner_id, concept_id)
        bkt_state = (
            BKTState(state.bkt_p, state.exercise_observations) if state else None
        )
        return estimate(concept_id, events, self.now(), bkt_state=bkt_state)

    def all_mastery(self) -> dict[str, MasteryView]:
        return {concept_id: self.mastery(concept_id) for concept_id in self.pack.concepts}

    def record(self, event: EvidenceEvent) -> None:
        now = self.now()
        for concept_id in event.concept_ids:
            if concept_id not in self.pack.concepts:
                continue
            existing = self.store.get_mastery(self.learner_id, concept_id)
            bkt = (
                BKTState(existing.bkt_p, existing.exercise_observations)
                if existing
                else initial_state()
            )
            other = existing.other_observations if existing else 0
            if event.kind == "exercise_attempt":
                bkt = observe(bkt, event.outcome == "correct")
            else:
                other += 1
            events = self.evidence.list(concept_id=concept_id, limit=1_000_000)
            rule = rule_score(events, concept_id, now)
            value = bkt.p if bkt.observations >= HANDOFF_OBSERVATIONS else rule.score
            self.store.upsert_mastery(
                MasteryState(
                    learner_id=self.learner_id,
                    concept_id=concept_id,
                    rule_score=rule.score,
                    bkt_p=bkt.p,
                    exercise_observations=bkt.observations,
                    other_observations=other,
                    estimate=value,
                    confidence=confidence_for(bkt.observations, other),
                    level=level_for(value),
                    updated_at=iso(now),
                )
            )
        if event.kind == "exercise_attempt" and event.exercise_id:
            previous = self.store.get_review(self.learner_id, event.exercise_id)
            self.store.upsert_review(
                review_event(
                    event.exercise_id,
                    event.concept_ids,
                    event,
                    previous=previous,
                    learner_id=self.learner_id,
                )
            )

    def due_reviews(self):
        return self.store.due_reviews(self.learner_id, self.now())

    def readiness(self) -> ReadinessView:
        return calculate_readiness(self.pack, self.goal(), self.all_mastery())

    def today_plan(self) -> DailyPlan:
        from testbridge.learning.weights import concept_weights

        return Planner(
            self.pack,
            self.goal(),
            self.all_mastery(),
            self.due_reviews(),
            concept_weights(self.pack, self.goal()),
        ).plan(self.now())
```

- [ ] **Step 4: Run the tests and commit**

The service imports `readiness` and `planner`, which are implemented in Tasks 8 and 9. Until then, the import fails. To keep Task 6 independently testable, temporarily implement the two methods with lazy imports inside `readiness()` / `today_plan()` (already lazy for `concept_weights`), and make `readiness.py` / `planner.py` stubs in this task:

```python
# src/testbridge/readiness.py
from dataclasses import dataclass


@dataclass(frozen=True)
class ReadinessView:
    total: float = 0.0


def calculate_readiness(pack, goal, mastery):
    return ReadinessView()
```

```python
# src/testbridge/recommend/planner.py
from dataclasses import dataclass


@dataclass(frozen=True)
class DailyPlan:
    items: list = None


class Planner:
    def __init__(self, *args, **kwargs):
        pass

    def plan(self, now):
        return DailyPlan(items=[])
```

Then run:

```bash
.venv/Scripts/python -m pytest tests/test_learning_service.py -q
git add src/testbridge/learning src/testbridge/readiness.py src/testbridge/recommend tests/test_learning_service.py
git commit -m "feat: add learning service"
```

Expected: 3 tests pass.

---

## Task 7: Rebuild Derived State

**Files:**
- Create: `src/testbridge/learning/rebuild.py`
- Test: `tests/test_rebuild.py`

**Interfaces:**
- Consumes: `LearningService`, `initial_state`, `observe`, `review_event`, `rule_score`, `level_for`, `confidence_for`, `HANDOFF_OBSERVATIONS`, `MasteryState`.
- Produces: `RebuildResult`, `rebuild_state(service) -> RebuildResult`.

- [ ] **Step 1: Write the failing tests**

```python
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.learning.rebuild import rebuild_state
from testbridge.learning.service import LearningService
from testbridge.learning.store import LearningStore

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def make_service(tmp_path: Path) -> LearningService:
    return LearningService(
        load_pack(SAMPLE), EvidenceStore(tmp_path / "e.db"),
        LearningStore(tmp_path / "l.db"), now_fn=lambda: NOW,
    )


def attempt(outcome: str, exercise_id: str = "EX-SYNC-001") -> object:
    item = new_event(
        kind="exercise_attempt", lesson_id="L-SYNC-001", exercise_id=exercise_id,
        concept_ids=["sensor-time-sync"], outcome=outcome,
        score=1.0 if outcome == "correct" else 0.0, max_score=1.0,
    )
    return replace(item, created_at=NOW.isoformat())


def comparable(service: LearningService) -> tuple:
    mastery = service.store.list_mastery("local")
    reviews = service.store.list_reviews("local")
    m = tuple(sorted(
        (key, value.rule_score, value.bkt_p, value.exercise_observations,
         value.other_observations, value.estimate, value.level)
        for key, value in mastery.items()
    ))
    r = tuple(sorted(
        (key, value.due, value.stability, value.difficulty, value.reps,
         value.lapses, value.state)
        for key, value in reviews.items()
    ))
    return m, r


def test_incremental_matches_rebuild(tmp_path: Path) -> None:
    incremental = make_service(tmp_path / "a")
    for outcome in ["correct", "incorrect", "correct"]:
        item = attempt(outcome)
        incremental.evidence.append(item)
        incremental.record(item)

    rebuilt = make_service(tmp_path / "b")
    for outcome in ["correct", "incorrect", "correct"]:
        rebuilt.evidence.append(attempt(outcome))
    rebuild_state(rebuilt)
    assert comparable(incremental) == comparable(rebuilt)


def test_rebuild_is_idempotent(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.evidence.append(attempt("correct"))
    first = rebuild_state(service)
    snapshot = comparable(service)
    second = rebuild_state(service)
    assert first == second
    assert comparable(service) == snapshot


def test_superseded_events_are_skipped(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    old = attempt("correct")
    correction = replace(attempt("incorrect"), supersedes=old.id)
    service.evidence.append(old)
    service.evidence.append(correction)
    rebuild_state(service)
    view = service.mastery("sensor-time-sync")
    assert view.estimate < 0.5
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_rebuild.py -q
```

Expected: import error for `testbridge.learning.rebuild`.

- [ ] **Step 3: Implement `rebuild.py`**

```python
"""Replay evidence into rebuildable mastery and review state."""

from __future__ import annotations

from dataclasses import dataclass

from testbridge.learning.service import LearningService
from testbridge.learning.store import MasteryState
from testbridge.learning.timeutil import iso
from testbridge.mastery.bkt import initial_state, observe
from testbridge.mastery.estimator import HANDOFF_OBSERVATIONS
from testbridge.mastery.rule import confidence_for, level_for, rule_score
from testbridge.schedule.fsrs import review_event


@dataclass(frozen=True)
class RebuildResult:
    events: int
    concepts: int
    reviews: int


def rebuild_state(service: LearningService) -> RebuildResult:
    events = sorted(
        service.evidence.list(limit=1_000_000),
        key=lambda event: (event.created_at, event.id),
    )
    superseded = {event.supersedes for event in events if event.supersedes}
    events = [event for event in events if event.id not in superseded]

    bkt = {concept_id: initial_state() for concept_id in service.pack.concepts}
    other = {concept_id: 0 for concept_id in service.pack.concepts}
    reviews = {}

    for event in events:
        for concept_id in event.concept_ids:
            if concept_id not in bkt:
                continue
            if event.kind == "exercise_attempt":
                bkt[concept_id] = observe(bkt[concept_id], event.outcome == "correct")
            else:
                other[concept_id] += 1
        if event.kind == "exercise_attempt" and event.exercise_id:
            reviews[event.exercise_id] = review_event(
                event.exercise_id,
                event.concept_ids,
                event,
                previous=reviews.get(event.exercise_id),
                learner_id=service.learner_id,
            )

    now = service.now()
    mastery = {}
    for concept_id in service.pack.concepts:
        rule = rule_score(events, concept_id, now)
        value = (
            bkt[concept_id].p
            if bkt[concept_id].observations >= HANDOFF_OBSERVATIONS
            else rule.score
        )
        mastery[concept_id] = MasteryState(
            learner_id=service.learner_id,
            concept_id=concept_id,
            rule_score=rule.score,
            bkt_p=bkt[concept_id].p,
            exercise_observations=bkt[concept_id].observations,
            other_observations=other[concept_id],
            estimate=value,
            confidence=confidence_for(bkt[concept_id].observations, other[concept_id]),
            level=level_for(value),
            updated_at=iso(now),
        )

    service.store.replace_all(service.learner_id, mastery, reviews)
    return RebuildResult(events=len(events), concepts=len(mastery), reviews=len(reviews))
```

- [ ] **Step 4: Run the tests and commit**

```bash
.venv/Scripts/python -m pytest tests/test_rebuild.py -q
git add src/testbridge/learning/rebuild.py tests/test_rebuild.py
git commit -m "feat: rebuild mastery and review state"
```

Expected: 3 tests pass.

---

## Task 8: Readiness and Concept Weights

**Files:**
- Create: `src/testbridge/learning/weights.py`
- Replace: `src/testbridge/readiness.py` (stub from Task 6)
- Modify: `src/testbridge/contract/models.py` (add `Module.priority`)
- Modify: `content-packs/sample-sensors/modules/M01/module.yaml` (add `priority: P0`)
- Modify: `tests/fixtures/minimal-pack/modules/M01/module.yaml` (add `priority: P1`)
- Test: `tests/test_readiness.py`

**Interfaces:**
- Consumes: `ContentPack`, `Goal`, `MasteryView`.
- Produces: `concept_weights(pack, goal) -> dict[str, float]`, `ReadinessView`, `calculate_readiness(pack, goal, mastery) -> ReadinessView`.

- [ ] **Step 1: Add `Module.priority`**

In `src/testbridge/contract/models.py`, update `Module`:

```python
class Module(StrictModel):
    schema_version: Literal["tb/1"] = Field(alias="schema")
    id: Id
    title: str = Field(min_length=1)
    priority: Literal["P0", "P1", "P2"] = "P1"
    concepts: list[Id] = Field(default_factory=list)
    lessons: list[Id] = Field(default_factory=list)
    order: int = 0
```

Add `priority: P0` to the sample module YAML and `priority: P1` to the fixture module YAML.

- [ ] **Step 2: Write the failing tests**

```python
from datetime import datetime, timezone

from testbridge.content.repository import load_pack
from testbridge.learning.store import Goal
from testbridge.mastery.estimator import MasteryView
from testbridge.readiness import calculate_readiness
from testbridge.learning.weights import concept_weights

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"
PACK = load_pack(SAMPLE)


def view(concept_id: str, estimate: float, level: str = "L2") -> MasteryView:
    return MasteryView(
        concept_id=concept_id, rule_score=estimate, bkt_p=estimate,
        estimate=estimate, confidence=1.0, level=level,
        exercise_observations=3, other_observations=0,
    )


def test_weights_use_module_priority_and_override() -> None:
    goal = Goal(learner_id="local", concept_overrides={"sensor-time-sync": 2.0})
    weights = concept_weights(PACK, goal)
    assert weights["sensor-time-sync"] == 2.0  # 1.0 * P0(1.0) * 2.0
    assert weights["timestamp-basics"] == 0.5  # 0.5 * P0(1.0)


def test_readiness_weighted_total() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 1.0, "L1"),
        "clock-drift": view("clock-drift", 0.0, "L2"),
        "sensor-time-sync": view("sensor-time-sync", 1.0, "L3"),
    }
    result = calculate_readiness(PACK, Goal(learner_id="local"), mastery)
    assert 0.0 < result.total <= 1.0
    assert result.gate_active is False
    assert "M01" in result.by_module


def test_p0_gate_caps_readiness() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 1.0, "L1"),
        "clock-drift": view("clock-drift", 1.0, "L2"),
        "sensor-time-sync": view("sensor-time-sync", 0.5, "L2"),  # target L3
    }
    result = calculate_readiness(PACK, Goal(learner_id="local"), mastery)
    assert result.gate_active is True
    assert result.total <= 0.7
    assert any("sensor-time-sync" in reason for reason in result.gate_reasons)
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_readiness.py -q
```

Expected: import error or `ReadinessView` missing fields.

- [ ] **Step 4: Implement `weights.py` and `readiness.py`**

`src/testbridge/learning/weights.py`:

```python
"""Readiness weights derived from content and goal."""

from __future__ import annotations

from testbridge.content.repository import ContentPack
from testbridge.learning.store import Goal

PRIORITY_MULTIPLIER = {"P0": 1.0, "P1": 0.7, "P2": 0.4}


def concept_weights(pack: ContentPack, goal: Goal) -> dict[str, float]:
    best_priority: dict[str, float] = {}
    for module in pack.modules.values():
        multiplier = PRIORITY_MULTIPLIER.get(module.priority, 0.7)
        for concept_id in module.concepts:
            best_priority[concept_id] = max(
                best_priority.get(concept_id, 0.0), multiplier
            )
    return {
        concept_id: concept.weight
        * best_priority.get(concept_id, 1.0)
        * goal.concept_overrides.get(concept_id, 1.0)
        for concept_id, concept in pack.concepts.items()
    }
```

`src/testbridge/readiness.py`:

```python
"""Weighted readiness score with a P0 gate."""

from __future__ import annotations

from dataclasses import dataclass, field

from testbridge.content.repository import ContentPack
from testbridge.learning.store import Goal
from testbridge.learning.weights import concept_weights
from testbridge.mastery.estimator import MasteryView

LEVEL_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}


@dataclass(frozen=True)
class ReadinessView:
    total: float
    by_module: dict[str, float] = field(default_factory=dict)
    gate_active: bool = False
    gate_reasons: list[str] = field(default_factory=list)
    breakdown: list[dict] = field(default_factory=list)


def calculate_readiness(
    pack: ContentPack,
    goal: Goal,
    mastery: dict[str, MasteryView],
) -> ReadinessView:
    weights = concept_weights(pack, goal)
    total_weight = sum(weights.values())
    total = (
        sum(weights[cid] * mastery[cid].estimate for cid in weights) / total_weight
        if total_weight
        else 0.0
    )

    by_module: dict[str, float] = {}
    for module in pack.modules.values():
        module_weight = sum(weights.get(cid, 0.0) for cid in module.concepts)
        by_module[module.id] = (
            sum(weights.get(cid, 0.0) * mastery[cid].estimate for cid in module.concepts)
            / module_weight
            if module_weight
            else 0.0
        )

    gate_reasons: list[str] = []
    for module in pack.modules.values():
        if module.priority != "P0":
            continue
        for concept_id in module.concepts:
            concept = pack.concepts.get(concept_id)
            view = mastery.get(concept_id)
            if concept is None or view is None:
                continue
            if LEVEL_ORDER[view.level] < LEVEL_ORDER[concept.target_level]:
                gate_reasons.append(
                    f"{concept_id} 估计 {view.level}，目标 {concept.target_level}"
                )

    if gate_reasons:
        total = min(total, 0.7)

    breakdown = [
        {
            "concept_id": cid,
            "weight": weights[cid],
            "mastery": mastery[cid].estimate,
            "level": mastery[cid].level,
            "target_level": pack.concepts[cid].target_level,
        }
        for cid in weights
    ]
    return ReadinessView(
        total=total,
        by_module=by_module,
        gate_active=bool(gate_reasons),
        gate_reasons=gate_reasons,
        breakdown=breakdown,
    )
```

- [ ] **Step 5: Run the tests and commit**

```bash
.venv/Scripts/python -m pytest tests/test_readiness.py -q
git add src/testbridge/learning/weights.py src/testbridge/readiness.py src/testbridge/contract/models.py content-packs/sample-sensors/modules/M01/module.yaml tests/fixtures/minimal-pack/modules/M01/module.yaml tests/test_readiness.py
git commit -m "feat: add readiness scoring"
```

Expected: 3 tests pass.

---

## Task 9: Daily Planner

**Files:**
- Replace: `src/testbridge/recommend/planner.py` (stub from Task 6)
- Test: `tests/test_planner.py`

**Interfaces:**
- Consumes: `ContentPack`, `Goal`, `MasteryView`, `ReviewState`, weights.
- Produces: `PlanItem`, `DailyPlan`, `Planner.plan(now)`.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timezone
from pathlib import Path

from testbridge.content.repository import load_pack
from testbridge.learning.store import Goal, ReviewState
from testbridge.mastery.estimator import MasteryView
from testbridge.recommend.planner import Planner

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"
PACK = load_pack(SAMPLE)
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def view(concept_id: str, estimate: float, observations: int = 0) -> MasteryView:
    return MasteryView(
        concept_id=concept_id, rule_score=estimate, bkt_p=estimate,
        estimate=estimate, confidence=1.0, level="L2",
        exercise_observations=observations, other_observations=0,
    )


def review(exercise_id: str) -> ReviewState:
    return ReviewState(
        learner_id="local", exercise_id=exercise_id, concept_ids=["sensor-time-sync"],
        due="2026-10-24T00:00:00+00:00", stability=1.0, difficulty=5.0,
        reps=1, lapses=0, state="Review", last_review=None,
        card_json={"card_id": 1, "state": 2, "step": 0, "stability": 1.0,
                   "difficulty": 5.0, "due": "2026-10-24T00:00:00+00:00",
                   "last_review": None},
    )


def test_due_reviews_come_first() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 1.0, 3),
        "clock-drift": view("clock-drift", 1.0, 3),
        "sensor-time-sync": view("sensor-time-sync", 1.0, 3),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery,
        [review("EX-SYNC-001")], {"sensor-time-sync": 1.0},
    )
    plan = planner.plan(NOW)
    assert plan.items
    assert plan.items[0].type == "review"
    assert plan.items[0].exercise_id == "EX-SYNC-001"


def test_new_concept_requires_prerequisites() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.0),
        "clock-drift": view("clock-drift", 0.0),
        "sensor-time-sync": view("sensor-time-sync", 0.0),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery, [],
        {"timestamp-basics": 0.5, "clock-drift": 0.5, "sensor-time-sync": 1.0},
    )
    plan = planner.plan(NOW)
    assert [item.type for item in plan.items] == ["new"]
    assert "timestamp-basics" in plan.items[0].concept_ids


def test_weak_concepts_are_added() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.2, 2),
        "clock-drift": view("clock-drift", 1.0, 3),
        "sensor-time-sync": view("sensor-time-sync", 0.2, 2),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery, [],
        {"timestamp-basics": 0.5, "clock-drift": 0.5, "sensor-time-sync": 1.0},
    )
    plan = planner.plan(NOW)
    assert any(item.type == "weak" for item in plan.items)


def test_budget_can_leave_only_reviews() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.0),
        "clock-drift": view("clock-drift", 0.0),
        "sensor-time-sync": view("sensor-time-sync", 0.0),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=10), mastery,
        [review("EX-SYNC-001")], {"timestamp-basics": 0.5},
    )
    plan = planner.plan(NOW)
    assert [item.type for item in plan.items] == ["review"]


def test_empty_plan_has_suggestion() -> None:
    mastery = {
        "timestamp-basics": view("timestamp-basics", 0.9, 5),
        "clock-drift": view("clock-drift", 0.9, 5),
        "sensor-time-sync": view("sensor-time-sync", 0.9, 5),
    }
    planner = Planner(
        PACK, Goal(learner_id="local", daily_minutes=45), mastery, [],
        {"timestamp-basics": 0.5},
    )
    plan = planner.plan(NOW)
    assert plan.empty is True
    assert plan.suggestion
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_planner.py -q
```

Expected: `Planner.plan` missing or returns empty stub.

- [ ] **Step 3: Implement `planner.py`**

```python
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
```

- [ ] **Step 4: Run the tests and commit**

```bash
.venv/Scripts/python -m pytest tests/test_planner.py -q
git add src/testbridge/recommend/planner.py tests/test_planner.py
git commit -m "feat: add deterministic daily planner"
```

Expected: 5 tests pass.

---

## Task 10: Web Pages and Learning Routes

**Files:**
- Modify: `web/app.py`
- Create: `web/templates/today.html`
- Create: `web/templates/concepts.html`
- Create: `web/templates/review.html`
- Modify: `web/templates/dashboard.html`
- Modify: `web/templates/progress.html`
- Test: `tests/test_web_p2.py`

**Interfaces:**
- Consumes: `LearningService`, `LearningStore`, `Planner`, `ReadinessView`.
- Produces: routes `/today`, `/concepts`, `/review`; dashboard/progress show readiness and mastery; `POST /api/evidence` updates learning state.

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from fastapi.testclient import TestClient

from web.app import create_app

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"


def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(SAMPLE, tmp_path / "test.db"))


def test_p2_pages_render(tmp_path: Path) -> None:
    c = client(tmp_path)
    assert c.get("/today").status_code == 200
    assert c.get("/concepts").status_code == 200
    assert c.get("/review").status_code == 200
    assert "sensor-time-sync" in c.get("/concepts").text
    assert "Readiness" in c.get("/").text


def test_today_shows_weak_after_wrong_answer(tmp_path: Path) -> None:
    c = client(tmp_path)
    c.post("/api/evidence", json={
        "lesson_id": "L-SYNC-001", "exercise_id": "EX-SYNC-001", "response": "wrong",
    })
    response = c.get("/today")
    assert response.status_code == 200
    assert "掌握度偏低" in response.text


def test_progress_includes_readiness(tmp_path: Path) -> None:
    c = client(tmp_path)
    response = c.get("/progress")
    assert response.status_code == 200
    assert "Readiness" in response.text
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_web_p2.py -q
```

Expected: 404 for the new routes or missing template.

- [ ] **Step 3: Wire `LearningService` into `create_app`**

In `web/app.py`:

```python
from testbridge.learning.service import LearningService
from testbridge.learning.store import LearningStore
```

Inside `create_app`, after `store = EvidenceStore(database)`:

```python
    learning_store = LearningStore(database)
    learning = LearningService(pack, store, learning_store)
```

Add `learning=learning` to `app.state` and to the `ctx` helper.

In `submit_evidence`, after `store.append(event)`:

```python
        learning.record(event)
```

- [ ] **Step 4: Add the routes**

```python
    @app.get("/today", response_class=HTMLResponse)
    def today_page(request: Request):
        plan = learning.today_plan()
        return templates.TemplateResponse(
            request=request, name="today.html", context=ctx(request, plan=plan)
        )

    @app.get("/concepts", response_class=HTMLResponse)
    def concepts_page(request: Request):
        views = learning.all_mastery()
        due = learning.due_reviews()
        due_counts: dict[str, int] = {}
        for review in due:
            for concept_id in review.concept_ids:
                due_counts[concept_id] = due_counts.get(concept_id, 0) + 1
        lesson_for_concept = {}
        for lesson in pack.lessons_in_order():
            for concept_id in lesson.manifest.concepts:
                lesson_for_concept.setdefault(concept_id, lesson.manifest.id)
        return templates.TemplateResponse(
            request=request, name="concepts.html",
            context=ctx(
                request, views=views, due_counts=due_counts,
                lesson_for_concept=lesson_for_concept,
            ),
        )

    @app.get("/review", response_class=HTMLResponse)
    def review_page(request: Request):
        due = learning.due_reviews()
        rows = []
        for review in due:
            lesson_id = next(
                (
                    lesson.manifest.id
                    for lesson in pack.lessons_in_order()
                    if review.exercise_id in lesson.manifest.exercises
                ),
                None,
            )
            rows.append({"review": review, "lesson_id": lesson_id})
        return templates.TemplateResponse(
            request=request, name="review.html", context=ctx(request, rows=rows)
        )
```

Update `/` dashboard context with `readiness=learning.readiness()`, `plan=learning.today_plan()`, `due_count=len(learning.due_reviews())`, and `weakest`:

```python
        views = learning.all_mastery()
        weakest = sorted(views.values(), key=lambda item: item.estimate)[:3]
```

Update `/progress` context with `readiness=learning.readiness()` and `views=learning.all_mastery()`.

- [ ] **Step 5: Add the templates**

`web/templates/today.html`:

```html
{% extends "base.html" %}
{% block title %}今日计划 · TestBridge{% endblock %}
{% block content %}
<h1>今日计划</h1>
<p>预算 {{ plan.budget_minutes }} 分钟，已排 {{ plan.total_minutes }} 分钟。</p>
{% if plan.empty %}
  <p>今天没有必须做的事。{% if plan.suggestion %}{{ plan.suggestion }}{% endif %}</p>
{% else %}
  <ol class="tb-plan">
  {% for item in plan.items %}
    <li>
      <strong>{{ item.type }}</strong> · {{ item.reason }} · {{ item.estimated_minutes }} 分钟
      {% if item.lesson_id %}<a href="/lesson/{{ item.lesson_id }}">打开课程</a>{% endif %}
      {% if item.exercise_id %}<span class="tb-meta">{{ item.exercise_id }}</span>{% endif %}
    </li>
  {% endfor %}
  </ol>
{% endif %}
{% endblock %}
```

`web/templates/concepts.html`:

```html
{% extends "base.html" %}
{% block title %}概念 · TestBridge{% endblock %}
{% block content %}
<h1>概念掌握度</h1>
<table>
<tr><th>概念</th><th>掌握度</th><th>等级</th><th>目标</th><th>到期</th><th>先修</th></tr>
{% for concept_id, view in views.items() %}
<tr>
  <td>{% if lesson_for_concept.get(concept_id) %}<a href="/lesson/{{ lesson_for_concept[concept_id] }}">{{ concept_id }}</a>{% else %}{{ concept_id }}{% endif %}</td>
  <td>{{ "%.2f"|format(view.estimate) }}</td>
  <td>{{ view.level }}</td>
  <td>{{ pack.concepts[concept_id].target_level }}</td>
  <td>{{ due_counts.get(concept_id, 0) }}</td>
  <td>{{ pack.concepts[concept_id].prerequisites|join(", ") }}</td>
</tr>
{% endfor %}
</table>
{% endblock %}
```

`web/templates/review.html`:

```html
{% extends "base.html" %}
{% block title %}复习 · TestBridge{% endblock %}
{% block content %}
<h1>到期复习</h1>
{% if not rows %}<p>今天没有到期卡。</p>{% else %}
<table>
<tr><th>练习</th><th>概念</th><th>到期</th><th>课程</th></tr>
{% for row in rows %}
<tr>
  <td>{{ row.review.exercise_id }}</td>
  <td>{{ row.review.concept_ids|join(", ") }}</td>
  <td>{{ row.review.due }}</td>
  <td>{% if row.lesson_id %}<a href="/lesson/{{ row.lesson_id }}">打开</a>{% endif %}</td>
</tr>
{% endfor %}
</table>
{% endif %}
{% endblock %}
```

Update `dashboard.html` to include readiness, due count, plan preview, weakest:

```html
<h2>Readiness {{ "%.2f"|format(readiness.total) }}</h2>
<p>到期复习 {{ due_count }} 张 · 今日计划 {{ plan.items|length }} 项</p>
{% if readiness.gate_active %}<p>门控：{{ readiness.gate_reasons|join("；") }}</p>{% endif %}
<h3>最弱概念</h3>
<ul>{% for item in weakest %}<li>{{ item.concept_id }} · {{ "%.2f"|format(item.estimate) }} · {{ item.level }}</li>{% endfor %}</ul>
```

Update `progress.html` to include:

```html
<h2>Readiness {{ "%.2f"|format(readiness.total) }}</h2>
{% if readiness.gate_active %}<p>门控：{{ readiness.gate_reasons|join("；") }}</p>{% endif %}
```

- [ ] **Step 6: Run tests and commit**

```bash
.venv/Scripts/python -m pytest tests/test_web.py tests/test_web_p2.py -q
git add web/app.py web/templates tests/test_web_p2.py
git commit -m "feat: add P2 learning pages"
```

Expected: all web tests pass.

---

## Task 11: CLI Commands

**Files:**
- Modify: `src/testbridge/cli.py`
- Test: `tests/test_cli_p2.py`

**Interfaces:**
- Consumes: `LearningService`, `LearningStore`, `rebuild_state`.
- Produces: `tb rebuild-state`, `tb goal show/set`, `tb readiness`, `tb today`.

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from testbridge.cli import main

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"


def test_rebuild_state_cli(tmp_path: Path, capsys) -> None:
    db = tmp_path / "l.db"
    assert main(["rebuild-state", "--pack", str(SAMPLE), "--db", str(db)]) == 0
    assert "rebuilt" in capsys.readouterr().out


def test_goal_set_and_show(tmp_path: Path, capsys) -> None:
    db = tmp_path / "l.db"
    assert main(["goal", "set", "--db", str(db), "--daily-minutes", "60"]) == 0
    assert main(["goal", "show", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "60" in out


def test_readiness_and_today(tmp_path: Path, capsys) -> None:
    db = tmp_path / "l.db"
    assert main(["readiness", "--pack", str(SAMPLE), "--db", str(db)]) == 0
    assert "readiness" in capsys.readouterr().out.lower()
    assert main(["today", "--pack", str(SAMPLE), "--db", str(db)]) == 0
    assert "today" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_cli_p2.py -q
```

Expected: argparse errors for unknown commands.

- [ ] **Step 3: Implement the CLI additions**

Add imports and helper:

```python
from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore
from testbridge.learning.rebuild import rebuild_state
from testbridge.learning.service import LearningService
from testbridge.learning.store import Goal, LearningStore


def _load_learning(pack_path: str, db_path: str, learner_id: str = "local") -> LearningService:
    pack = load_pack(Path(pack_path))
    return LearningService(
        pack, EvidenceStore(Path(db_path)), LearningStore(Path(db_path)), learner_id
    )
```

Add subparsers:

```python
    rebuild = sub.add_parser("rebuild-state")
    rebuild.add_argument("--pack", default="content-packs/sample-sensors")
    rebuild.add_argument("--db", default="data/testbridge.db")
    rebuild.add_argument("--learner-id", default="local")

    goal = sub.add_parser("goal")
    goal_sub = goal.add_subparsers(dest="goal_command", required=True)
    goal_show = goal_sub.add_parser("show")
    goal_show.add_argument("--db", default="data/testbridge.db")
    goal_show.add_argument("--learner-id", default="local")
    goal_set = goal_sub.add_parser("set")
    goal_set.add_argument("--db", default="data/testbridge.db")
    goal_set.add_argument("--learner-id", default="local")
    goal_set.add_argument("--target-role", default="")
    goal_set.add_argument("--weekly-hours", type=float, default=0.0)
    goal_set.add_argument("--daily-minutes", type=int, default=45)
    goal_set.add_argument("--override", action="append", default=[])

    readiness = sub.add_parser("readiness")
    readiness.add_argument("--pack", default="content-packs/sample-sensors")
    readiness.add_argument("--db", default="data/testbridge.db")
    readiness.add_argument("--learner-id", default="local")

    today = sub.add_parser("today")
    today.add_argument("--pack", default="content-packs/sample-sensors")
    today.add_argument("--db", default="data/testbridge.db")
    today.add_argument("--learner-id", default="local")
```

Add handlers:

```python
    if args.command == "rebuild-state":
        service = _load_learning(args.pack, args.db, args.learner_id)
        result = rebuild_state(service)
        print(f"rebuilt {result.events} events, {result.concepts} concepts, {result.reviews} reviews")
        return 0

    if args.command == "goal":
        if args.goal_command == "show":
            goal = LearningStore(Path(args.db)).get_goal(args.learner_id)
            print(goal)
            return 0
        overrides = {}
        for item in args.override:
            key, _, value = item.partition("=")
            overrides[key] = float(value)
        LearningStore(Path(args.db)).set_goal(Goal(
            learner_id=args.learner_id, target_role=args.target_role,
            weekly_hours=args.weekly_hours, daily_minutes=args.daily_minutes,
            concept_overrides=overrides,
        ))
        print("goal updated")
        return 0

    if args.command == "readiness":
        service = _load_learning(args.pack, args.db, args.learner_id)
        view = service.readiness()
        print(f"readiness: {view.total:.2f}")
        for module_id, value in view.by_module.items():
            print(f"  {module_id}: {value:.2f}")
        for reason in view.gate_reasons:
            print(f"  gate: {reason}")
        return 0

    if args.command == "today":
        service = _load_learning(args.pack, args.db, args.learner_id)
        plan = service.today_plan()
        print(f"today: {len(plan.items)} items, {plan.total_minutes}/{plan.budget_minutes} minutes")
        for item in plan.items:
            print(f"  {item.type}: {item.reason} ({item.estimated_minutes}m)")
        if plan.empty:
            print(f"  {plan.suggestion or 'no mandatory work'}")
        return 0
```

- [ ] **Step 4: Run tests and commit**

```bash
.venv/Scripts/python -m pytest tests/test_cli_p2.py -q
git add src/testbridge/cli.py tests/test_cli_p2.py
git commit -m "feat: add P2 CLI commands"
```

Expected: 3 tests pass.

---

## Task 12: E2E, Docs, and Final Verification

**Files:**
- Create: `tests/test_e2e_p2.py`
- Modify: `README.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/superpowers/specs/2026-10-25-p2-learning-loop-design.md` (status → Approved)

**Interfaces:**
- Produces: end-to-end proof and updated docs.

- [ ] **Step 1: Write the end-to-end test**

```python
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.learning.rebuild import rebuild_state
from testbridge.learning.service import LearningService
from testbridge.learning.store import LearningStore
from web.app import create_app

SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def test_learning_loop_end_to_end(tmp_path: Path) -> None:
    service = LearningService(
        load_pack(SAMPLE), EvidenceStore(tmp_path / "e.db"),
        LearningStore(tmp_path / "l.db"), now_fn=lambda: NOW,
    )
    for outcome in ["correct", "correct", "correct"]:
        event = new_event(
            kind="exercise_attempt", lesson_id="L-SYNC-001",
            exercise_id="EX-SYNC-001", concept_ids=["sensor-time-sync"],
            outcome=outcome, score=1.0, max_score=1.0,
        )
        service.evidence.append(event)
    rebuild_state(service)
    view = service.mastery("sensor-time-sync")
    assert view.exercise_observations == 3
    assert view.estimate == view.bkt_p
    assert service.store.list_reviews("local")
    assert 0.0 <= service.readiness().total <= 1.0
    plan = service.today_plan()
    assert plan.budget_minutes == 45


def test_p2_web_pages_on_sample_pack(tmp_path: Path) -> None:
    c = TestClient(create_app(SAMPLE, tmp_path / "web.db"))
    assert c.get("/today").status_code == 200
    assert c.get("/concepts").status_code == 200
    assert c.get("/review").status_code == 200
    assert c.get("/").status_code == 200
```

- [ ] **Step 2: Run the full suite**

```bash
.venv/Scripts/python -m pytest -q
```

Expected: all P1 + P2 tests pass.

- [ ] **Step 3: Run the CLI smoke**

```bash
.venv/Scripts/python -m testbridge.cli validate content-packs/sample-sensors
.venv/Scripts/python -m testbridge.cli rebuild-state --pack content-packs/sample-sensors --db data/testbridge.db
.venv/Scripts/python -m testbridge.cli readiness --pack content-packs/sample-sensors --db data/testbridge.db
.venv/Scripts/python -m testbridge.cli today --pack content-packs/sample-sensors --db data/testbridge.db
```

Expected: validate 0/0; rebuild/readiness/today exit 0 with output.

- [ ] **Step 4: Update docs**

- `README.md`: add `tb rebuild-state`, `tb goal set`, `tb readiness`, `tb today` to the quick start.
- `docs/ROADMAP.md`: set the current phase to P2, status “实现完成，待验收”; add P2 carry-forwards if any.
- P2 spec: status `Approved，2026-10-25`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_e2e_p2.py README.md docs/ROADMAP.md docs/superpowers/specs/2026-10-25-p2-learning-loop-design.md
git commit -m "test: verify P2 learning loop end to end"
```

---

## Self-Review Checklist

- [ ] Every P2 spec section has a task: mastery, BKT, FSRS, readiness, planner, dashboard, CLI, rebuild, P1 carry-forwards.
- [ ] `LearningStore.replace_all` takes `learner_id` and clears stale rows.
- [ ] `Module.priority` added and used by weights.
- [ ] `ReadinessView` fields match the spec: `total`, `by_module`, `gate_active`, `gate_reasons`, `breakdown`.
- [ ] `DailyPlan`/`PlanItem` fields match the spec.
- [ ] `LearningService` methods used by web/CLI exist: `mastery`, `all_mastery`, `record`, `due_reviews`, `readiness`, `today_plan`, `goal`.
- [ ] `fsrs` dependency pinned and scheduler configured with empty steps.
- [ ] No task implements P3/P4 features.
- [ ] P1 118 tests remain green.
- [ ] No placeholders or undefined interfaces.

