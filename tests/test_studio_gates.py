import shutil
from pathlib import Path

import pytest

from testbridge.studio.gates import PromoteError, promote, validate_draft, verify_resources
from testbridge.studio.store import DraftStore

FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "minimal-pack"


def make_draft(tmp_path: Path, draft_id: str = "demo") -> DraftStore:
    store = DraftStore(tmp_path / "drafts")
    store.create(
        draft_id=draft_id, topic="t", level="L2", lesson_count=1,
        searches_per_lesson=5, model="m", prompt_version="studio/1",
    )
    return store


def test_validate_reports_errors_for_empty_draft(tmp_path: Path) -> None:
    store = make_draft(tmp_path)
    summary = validate_draft(store, "demo")
    assert summary.errors


def test_promote_copies_only_content_files(tmp_path: Path) -> None:
    store = make_draft(tmp_path, "minimal")
    shutil.copytree(FIXTURE, store.path("minimal"), dirs_exist_ok=True)
    store.write("minimal", "outline.html", "<article>x</article>")
    store.write("minimal", "research/L-ONE.html", "<article>r</article>")

    target = promote(store, "minimal", tmp_path / "packs", verifier=lambda items: [])

    assert (target / "pack.yaml").is_file()
    assert not (target / "draft.json").exists()
    assert not (target / "outline.html").exists()
    assert not (target / "research").exists()


def test_promote_refuses_existing_pack(tmp_path: Path) -> None:
    store = make_draft(tmp_path, "minimal")
    packs = tmp_path / "packs"
    (packs / "minimal").mkdir(parents=True)
    with pytest.raises(PromoteError):
        promote(store, "minimal", packs, verifier=lambda items: [])


def test_promote_skip_verify_does_not_check_resources(tmp_path: Path) -> None:
    store = make_draft(tmp_path, "minimal")
    shutil.copytree(FIXTURE, store.path("minimal"), dirs_exist_ok=True)

    def verifier(items):
        raise AssertionError("verifier should not run")

    promote(
        store, "minimal", tmp_path / "packs",
        skip_verify=True, verifier=verifier,
    )


def test_verify_resources_reports_unreachable() -> None:
    class FakeResponse:
        def __init__(self, code: int) -> None:
            self.status_code = code

    class FakeClient:
        def __init__(self, codes: dict[str, int]) -> None:
            self.codes = codes

        def get(self, url: str, **kwargs):
            return FakeResponse(self.codes.get(url, 200))

    resources = [
        {"id": "DOC-1", "url": "https://ok.example"},
        {"id": "DOC-2", "url": "https://bad.example"},
    ]
    errors = verify_resources(
        resources, client=FakeClient({"https://bad.example": 404})
    )
    assert errors == ["DOC-2: HTTP 404"]
