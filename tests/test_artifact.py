from pathlib import Path

import pytest

from testbridge.artifact import ArtifactError, save_artifact
from testbridge.contract.models import ArtifactSpec

SPEC = ArtifactSpec(accept=["log", "txt", "md"], max_size_mb=1)


def test_saves_file_under_evidence_directory(tmp_path: Path) -> None:
    stored = save_artifact(tmp_path, "ev-1", "run.log", b"hello", SPEC)

    assert stored.path == tmp_path / "ev-1" / "run.log"
    assert stored.path.read_bytes() == b"hello"
    assert stored.size == 5
    assert stored.filename == "run.log"


def test_rejects_unsupported_extension(tmp_path: Path) -> None:
    with pytest.raises(ArtifactError) as excinfo:
        save_artifact(tmp_path, "ev-1", "run.exe", b"x", SPEC)
    assert excinfo.value.code == "artifact_type"


def test_rejects_empty_file(tmp_path: Path) -> None:
    with pytest.raises(ArtifactError) as excinfo:
        save_artifact(tmp_path, "ev-1", "run.log", b"", SPEC)
    assert excinfo.value.code == "artifact_size"


def test_rejects_oversized_file(tmp_path: Path) -> None:
    payload = b"x" * (SPEC.max_size_mb * 1024 * 1024 + 1)
    with pytest.raises(ArtifactError) as excinfo:
        save_artifact(tmp_path, "ev-1", "run.log", payload, SPEC)
    assert excinfo.value.code == "artifact_size"


def test_rejects_path_traversal_names(tmp_path: Path) -> None:
    with pytest.raises(ArtifactError) as excinfo:
        save_artifact(tmp_path, "ev-1", "../../evil.log", b"x", SPEC)
    assert excinfo.value.code == "artifact_name"


def test_keeps_only_basename_for_nested_paths(tmp_path: Path) -> None:
    stored = save_artifact(tmp_path, "ev-1", "logs/run.log", b"x", SPEC)
    assert stored.filename == "run.log"


def test_accepts_chinese_filename(tmp_path: Path) -> None:
    stored = save_artifact(tmp_path, "ev-1", "测试日志.log", b"x", SPEC)
    assert stored.filename == "测试日志.log"
