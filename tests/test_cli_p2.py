from pathlib import Path

import pytest

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


def test_goal_set_merges_unspecified_fields(tmp_path: Path, capsys) -> None:
    db = tmp_path / "l.db"
    assert main(
        [
            "goal", "set", "--db", str(db),
            "--target-role", "embodied-ai-test-engineer",
            "--weekly-hours", "10",
            "--daily-minutes", "45",
            "--override", "sensor-time-sync=1.5",
        ]
    ) == 0
    assert main(["goal", "set", "--db", str(db), "--daily-minutes", "60"]) == 0
    capsys.readouterr()
    assert main(["goal", "show", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "embodied-ai-test-engineer" in out
    assert "10.0" in out
    assert "sensor-time-sync" in out
    assert "60" in out


def test_goal_set_override_round_trip(tmp_path: Path, capsys) -> None:
    db = tmp_path / "l.db"
    assert main(
        ["goal", "set", "--db", str(db), "--override", "sensor-time-sync=1.5"]
    ) == 0
    capsys.readouterr()
    assert main(["goal", "show", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "sensor-time-sync" in out
    assert "1.5" in out


@pytest.mark.parametrize(
    "args",
    [
        ["--override", "x=abc"],
        ["--override", "x"],
        ["--override", "x=-1"],
        ["--daily-minutes", "0"],
        ["--weekly-hours", "nan"],
        ["--weekly-hours", "inf"],
    ],
)
def test_goal_set_rejects_invalid_input(tmp_path: Path, capsys, args: list[str]) -> None:
    db = tmp_path / "l.db"
    assert main(["goal", "set", "--db", str(db), *args]) == 2
    captured = capsys.readouterr()
    assert "ERROR goal:" in captured.err
    assert "Traceback" not in captured.err
