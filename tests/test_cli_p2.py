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
