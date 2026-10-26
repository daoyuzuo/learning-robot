import shutil
from pathlib import Path

import yaml

from testbridge.content.repository import load_pack
from testbridge.contract.models import Resource
from testbridge.contract.validator import validate_pack

FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "minimal-pack"


def rewrite_resources(root: Path, **overrides) -> None:
    path = root / "resources.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["resources"][0].update(overrides)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def test_resource_defaults() -> None:
    resource = Resource(
        id="R-1", title="t", url="https://example.com", type="paper", trust="A"
    )
    assert resource.kind == "other"
    assert resource.role == "required"


def test_rejects_unknown_kind() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Resource(
            id="R-1", title="t", url="https://example.com", type="paper",
            trust="A", kind="podcast",
        )


def test_old_pack_kind_derived_from_type(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    shutil.copytree(FIXTURE, root)
    rewrite_resources(root, type="paper")

    pack = load_pack(root)

    assert pack.resources["DOC-ONE"].kind == "paper"
    assert pack.resources["DOC-ONE"].role == "required"


def test_explicit_kind_wins_over_type(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    shutil.copytree(FIXTURE, root)
    rewrite_resources(root, type="paper", kind="official_docs")

    pack = load_pack(root)

    assert pack.resources["DOC-ONE"].kind == "official_docs"


def test_validator_rejects_required_c(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    shutil.copytree(FIXTURE, root)
    rewrite_resources(root, trust="C")

    report = validate_pack(root)

    assert any(issue.code == "resource.required_trust" for issue in report.errors)


def test_validator_allows_supplementary_c(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    shutil.copytree(FIXTURE, root)
    rewrite_resources(root, trust="C", role="supplementary")

    report = validate_pack(root)

    assert report.errors == []


def test_validator_rejects_d_for_any_role(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    shutil.copytree(FIXTURE, root)
    rewrite_resources(root, trust="D", role="supplementary")

    report = validate_pack(root)

    assert any(issue.code == "resource.trust" for issue in report.errors)
