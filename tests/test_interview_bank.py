from pathlib import Path

import pytest

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
    with pytest.raises(InterviewBankError):
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
