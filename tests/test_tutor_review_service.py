import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from testbridge.content.repository import load_pack
from testbridge.evidence.store import EvidenceStore, new_event
from testbridge.learning.service import LearningService
from testbridge.learning.store import LearningStore
from testbridge.tutor.client import TutorUpstreamError
from testbridge.tutor.config import TutorConfig
from testbridge.tutor.review_service import (
    EvidenceNotFoundError,
    ReviewService,
    UnsupportedEvidenceError,
)
from testbridge.tutor.review_store import ExerciseReviewStore

PACK = load_pack(Path(__file__).parents[1] / "content-packs" / "ros2-qos")
CONFIG = TutorConfig(
    base_url="https://api.example.com/v1",
    api_key="sk-test",
    model="demo-model",
    timeout=5.0,
)
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
REPLY = (
    '{"verdict": "partial", "explanation": "方向对，但漏了重传代价。", '
    '"strengths": ["方向对"], "gaps": ["没提重传"], '
    '"rubric": [{"dimension": "机制", "met": true, "comment": "对"}, '
    '{"dimension": "场景", "met": false, "comment": "缺反例"}], '
    '"suggested_score": 0.5}'
)


class FakeClient:
    def __init__(self, reply: str = REPLY, error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.reply


def setup_env(tmp_path: Path, client: FakeClient):
    db = tmp_path / "e.db"
    evidence = EvidenceStore(db)
    service = ReviewService(
        PACK, evidence, ExerciseReviewStore(db), client, CONFIG
    )
    return evidence, service


def short_answer_attempt(evidence: EvidenceStore):
    event = replace(
        new_event(
            kind="exercise_attempt",
            lesson_id="L-QOS-002",
            exercise_id="EX-QOS-005",
            concept_ids=["dds-qos-policies"],
            outcome="incorrect",
            score=0.0,
            max_score=1.0,
            payload={"response": "depth 是时间，lifespan 是数量"},
        ),
        created_at=NOW.isoformat(),
    )
    evidence.append(event)
    return event


def test_review_returns_parsed_result_and_evidence_event(tmp_path: Path) -> None:
    client = FakeClient()
    evidence, service = setup_env(tmp_path, client)
    attempt = short_answer_attempt(evidence)

    reply = service.review(attempt.id)

    assert reply.cached is False
    assert reply.saved is True
    assert reply.review.verdict == "partial"
    assert reply.review.suggested_score == 0.5
    assert reply.evidence_event is not None
    assert reply.evidence_event.kind == "llm_review"
    assert reply.evidence_event.score == 0.5
    assert reply.evidence_event.payload["evidence_id"] == attempt.id
    assert reply.evidence_event.payload["prompt_version"] == "review/1"
    assert client.calls == 1


def test_choice_attempt_has_no_reference_score(tmp_path: Path) -> None:
    client = FakeClient()
    evidence, service = setup_env(tmp_path, client)
    event = replace(
        new_event(
            kind="exercise_attempt", lesson_id="L-QOS-002",
            exercise_id="EX-QOS-002", concept_ids=["dds-qos-policies"],
            outcome="incorrect", score=0.0, max_score=1.0,
            payload={"response": "a"},
        ),
        created_at=NOW.isoformat(),
    )
    evidence.append(event)

    reply = service.review(event.id)

    assert reply.evidence_event is None
    assert reply.review.suggested_score is None


def test_cache_prevents_second_call(tmp_path: Path) -> None:
    client = FakeClient()
    evidence, service = setup_env(tmp_path, client)
    attempt = short_answer_attempt(evidence)

    service.review(attempt.id)
    second = service.review(attempt.id)

    assert client.calls == 1
    assert second.cached is True
    assert second.evidence_event is None
    assert second.review.verdict == "partial"


def test_refresh_calls_again_and_supersedes(tmp_path: Path) -> None:
    client = FakeClient()
    evidence, service = setup_env(tmp_path, client)
    attempt = short_answer_attempt(evidence)

    first = service.review(attempt.id)
    evidence.append(first.evidence_event)   # web 层在返回后立即落库
    second = service.review(attempt.id, refresh=True)

    assert client.calls == 2
    assert second.cached is False
    assert second.evidence_event.supersedes == first.evidence_event.id


def test_unknown_evidence_is_rejected(tmp_path: Path) -> None:
    _, service = setup_env(tmp_path, FakeClient())
    with pytest.raises(EvidenceNotFoundError):
        service.review("nope")


def test_other_learner_evidence_is_hidden(tmp_path: Path) -> None:
    client = FakeClient()
    evidence, service = setup_env(tmp_path, client)
    short_answer_attempt(evidence)
    hidden = replace(
        new_event(
            kind="exercise_attempt", lesson_id="L-QOS-002",
            exercise_id="EX-QOS-005", concept_ids=["dds-qos-policies"],
            outcome="incorrect", score=0.0, max_score=1.0,
            payload={"response": "x"}, learner_id="other",
        ),
        created_at=NOW.isoformat(),
    )
    evidence.append(hidden)

    with pytest.raises(EvidenceNotFoundError):
        service.review(hidden.id)


def test_llm_review_evidence_is_unsupported(tmp_path: Path) -> None:
    _, service = setup_env(tmp_path, FakeClient())
    event = new_event(kind="llm_review", concept_ids=["dds-qos-policies"])
    service.evidence.append(event)

    with pytest.raises(UnsupportedEvidenceError):
        service.review(event.id)


def test_upstream_error_propagates(tmp_path: Path) -> None:
    client = FakeClient(error=TutorUpstreamError("boom"))
    evidence, service = setup_env(tmp_path, client)
    attempt = short_answer_attempt(evidence)

    with pytest.raises(TutorUpstreamError):
        service.review(attempt.id)


def test_review_does_not_change_mastery(tmp_path: Path) -> None:
    client = FakeClient()
    db = tmp_path / "e.db"
    evidence = EvidenceStore(db)
    learning = LearningService(PACK, evidence, LearningStore(db), now_fn=lambda: NOW)
    service = ReviewService(PACK, evidence, ExerciseReviewStore(db), client, CONFIG)
    attempt = short_answer_attempt(evidence)
    learning.record(attempt)
    before = learning.all_mastery()
    before_readiness = learning.readiness(before)

    reply = service.review(attempt.id)
    evidence.append(reply.evidence_event)
    learning.record(reply.evidence_event)

    assert learning.all_mastery() == before
    assert learning.readiness() == before_readiness


def test_store_failure_still_returns_review(tmp_path: Path) -> None:
    class BrokenStore(ExerciseReviewStore):
        def put(self, **kwargs):
            raise sqlite3.OperationalError("disk full")

    db = tmp_path / "e.db"
    evidence = EvidenceStore(db)
    service = ReviewService(PACK, evidence, BrokenStore(db), FakeClient(), CONFIG)
    attempt = short_answer_attempt(evidence)

    reply = service.review(attempt.id)

    assert reply.saved is False
    assert reply.review.explanation
    assert reply.evidence_event is not None
