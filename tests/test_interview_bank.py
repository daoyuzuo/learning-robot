from pathlib import Path

import pytest

from testbridge.content.repository import load_pack
from testbridge.interview.bank import (
    InterviewBankError,
    load_bank,
    resolve_bank_path,
)

VALID = """\
schema: tb-interview/1
pack: sample-sensors
questions:
  - id: q-one
    title: 时间戳含义
    prompt: 时间戳代表哪个时刻？
    concepts: [timestamp-basics]
    level: L1
    minutes: 5
    reference_points: [事件发生时刻]
    rubric:
      - {dimension: 准确性, weight: 0.6, criteria: 说清事件时刻}
      - {dimension: 影响, weight: 0.4, criteria: 说清打点位置}
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "bank.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_valid_bank(tmp_path: Path) -> None:
    bank = load_bank(
        write(tmp_path, VALID),
        pack_id="sample-sensors",
        concept_ids={"timestamp-basics"},
    )
    assert bank.pack == "sample-sensors"
    assert [question.id for question in bank.questions] == ["q-one"]
    assert bank.questions[0].rubric[0].dimension == "准确性"


def test_rejects_missing_concept(tmp_path: Path) -> None:
    with pytest.raises(InterviewBankError, match="不存在的概念"):
        load_bank(
            write(tmp_path, VALID),
            pack_id="sample-sensors",
            concept_ids={"other-concept"},
        )


def test_rejects_pack_mismatch(tmp_path: Path) -> None:
    with pytest.raises(InterviewBankError, match="pack"):
        load_bank(
            write(tmp_path, VALID),
            pack_id="ros2-qos",
            concept_ids={"timestamp-basics"},
        )


def test_rejects_duplicate_ids(tmp_path: Path) -> None:
    text = VALID + (
        "  - id: q-one\n"
        "    title: 重复\n"
        "    prompt: 重复\n"
        "    concepts: [timestamp-basics]\n"
        "    level: L1\n"
        "    rubric:\n"
        "      - {dimension: 准确性, weight: 1.0, criteria: 说清}\n"
    )
    with pytest.raises(InterviewBankError, match="unique"):
        load_bank(write(tmp_path, text), pack_id="sample-sensors",
                  concept_ids={"timestamp-basics"})


def test_rejects_bad_weight_sum(tmp_path: Path) -> None:
    text = VALID.replace("weight: 0.4", "weight: 0.5")
    with pytest.raises(InterviewBankError, match="weights must sum"):
        load_bank(write(tmp_path, text), pack_id="sample-sensors",
                  concept_ids={"timestamp-basics"})


def test_rejects_duplicate_dimensions(tmp_path: Path) -> None:
    text = VALID.replace("dimension: 影响", "dimension: 准确性")
    with pytest.raises(InterviewBankError, match="unique"):
        load_bank(write(tmp_path, text), pack_id="sample-sensors",
                  concept_ids={"timestamp-basics"})


def test_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InterviewBankError, match="无法读取"):
        load_bank(tmp_path / "nope.yaml", pack_id="sample-sensors",
                  concept_ids={"timestamp-basics"})


def test_resolve_prefers_in_pack(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    banks_root = tmp_path / "banks"
    pack_root.mkdir()
    banks_root.mkdir()
    (pack_root / "interviews.yaml").write_text(VALID, encoding="utf-8")
    (banks_root / "sample-sensors.yaml").write_text(VALID, encoding="utf-8")
    assert resolve_bank_path(pack_root, "sample-sensors", banks_root) == (
        pack_root / "interviews.yaml"
    )


def test_resolve_falls_back_to_app_layer(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    banks_root = tmp_path / "banks"
    pack_root.mkdir()
    banks_root.mkdir()
    target = banks_root / "sample-sensors.yaml"
    target.write_text(VALID, encoding="utf-8")
    assert resolve_bank_path(pack_root, "sample-sensors", banks_root) == target
    assert resolve_bank_path(pack_root, "missing", banks_root) is None


ROOT = Path(__file__).parents[1]


def test_sample_bank_matches_pack() -> None:
    pack = load_pack(ROOT / "content-packs" / "sample-sensors")
    path = resolve_bank_path(
        pack.root, pack.meta.id, ROOT / "interview-banks"
    )
    assert path is not None
    bank = load_bank(path, pack_id=pack.meta.id, concept_ids=set(pack.concepts))
    assert len(bank.questions) == 3
    assert {cid for q in bank.questions for cid in q.concepts} == set(pack.concepts)


def test_ros2_bank_matches_pack() -> None:
    pack = load_pack(ROOT / "content-packs" / "ros2-qos")
    path = resolve_bank_path(
        pack.root, pack.meta.id, ROOT / "interview-banks"
    )
    assert path is not None
    bank = load_bank(path, pack_id=pack.meta.id, concept_ids=set(pack.concepts))
    assert len(bank.questions) == 15
    assert {cid for q in bank.questions for cid in q.concepts} == set(pack.concepts)


NO_RUBRIC = """\
schema: tb-interview/1
pack: sample-sensors
questions:
  - id: q-no-rubric
    title: 无 rubric
    prompt: 题目
    concepts: [timestamp-basics]
    level: L1
    rubric: []
"""


def test_rejects_wrong_schema(tmp_path: Path) -> None:
    text = VALID.replace("schema: tb-interview/1", "schema: tb-interview/2")
    with pytest.raises(InterviewBankError):
        load_bank(write(tmp_path, text), pack_id="sample-sensors",
                  concept_ids={"timestamp-basics"})


def test_rejects_empty_bank(tmp_path: Path) -> None:
    text = "schema: tb-interview/1\npack: sample-sensors\nquestions: []\n"
    with pytest.raises(InterviewBankError):
        load_bank(write(tmp_path, text), pack_id="sample-sensors",
                  concept_ids={"timestamp-basics"})


def test_rejects_empty_rubric(tmp_path: Path) -> None:
    with pytest.raises(InterviewBankError, match="rubric must not be empty"):
        load_bank(write(tmp_path, NO_RUBRIC), pack_id="sample-sensors",
                  concept_ids={"timestamp-basics"})


def test_by_id_and_concepts_with_questions(tmp_path: Path) -> None:
    bank = load_bank(write(tmp_path, VALID), pack_id="sample-sensors",
                     concept_ids={"timestamp-basics"})
    assert bank.by_id("q-one").title == "时间戳含义"
    with pytest.raises(KeyError):
        bank.by_id("missing")
    assert bank.concepts_with_questions() == ["timestamp-basics"]
