import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI

from testbridge.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"
ROOT = Path(__file__).resolve().parents[1]


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


def test_python_dash_m_invokes_cli() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "testbridge.cli", "validate", "tests/fixtures/minimal-pack"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0
    assert "0 error(s)" in result.stdout
    assert result.stderr == ""


def test_load_app_from_repo_checkout(tmp_path: Path, monkeypatch) -> None:
    from testbridge.cli import _load_app

    monkeypatch.setattr(
        sys,
        "path",
        [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT],
    )
    monkeypatch.delitem(sys.modules, "web.app", raising=False)
    monkeypatch.delitem(sys.modules, "web", raising=False)

    app = _load_app(FIXTURE, tmp_path / "serve.db")

    assert isinstance(app, FastAPI)
    assert app.title == "TestBridge"
    assert str(ROOT) in sys.path
