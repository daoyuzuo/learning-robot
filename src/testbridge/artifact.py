"""Store uploaded artifacts without putting binaries into evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from testbridge.contract.models import ArtifactSpec

NAME_RE = re.compile(r"^[\w.\-]{1,80}$", re.UNICODE)
BYTES_PER_MB = 1024 * 1024


@dataclass(frozen=True)
class StoredArtifact:
    path: Path
    filename: str
    size: int


class ArtifactError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _filename(raw: str) -> str:
    parts = [item for item in raw.replace("\\", "/").split("/") if item not in {"", "."}]
    if not parts or any(item == ".." for item in parts):
        raise ArtifactError("artifact_name", "文件名不合法")
    name = parts[-1].strip()
    if name in {"", ".", ".."} or not NAME_RE.fullmatch(name):
        raise ArtifactError("artifact_name", "文件名不合法")
    return name


def _extension(name: str) -> str:
    _, dot, suffix = name.rpartition(".")
    return suffix.lower() if dot else ""


def save_artifact(
    root: Path,
    evidence_id: str,
    filename: str,
    data: bytes,
    spec: ArtifactSpec,
) -> StoredArtifact:
    name = _filename(filename)
    if _extension(name) not in {item.lower().lstrip(".") for item in spec.accept}:
        raise ArtifactError("artifact_type", f"不支持的文件类型：{name}")

    size = len(data)
    if size == 0:
        raise ArtifactError("artifact_size", "文件为空")
    if size > spec.max_size_mb * BYTES_PER_MB:
        raise ArtifactError("artifact_size", f"文件超过 {spec.max_size_mb} MB")

    directory = root / evidence_id
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    temporary = directory / f".{name}.part"
    temporary.write_bytes(data)
    temporary.replace(target)
    return StoredArtifact(path=target, filename=name, size=size)
