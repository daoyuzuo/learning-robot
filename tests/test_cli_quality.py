import json
import shutil
from pathlib import Path

from testbridge.cli import main
from testbridge.content.repository import load_pack

FIXTURE = Path(__file__).parent / "fixtures" / "minimal-pack"
SAMPLE = Path(__file__).parents[1] / "content-packs" / "sample-sensors"
QOS = Path(__file__).parents[1] / "content-packs" / "ros2-qos"


def test_quality_minimal_fixture_fails(capsys) -> None:
    assert main(["quality", str(FIXTURE)]) == 1
    out = capsys.readouterr().out
    assert "quality:" in out
    assert "lesson_too_few_exercises" in out
    assert "lesson_level_short" in out


def test_quality_sample_sensors_passes(capsys) -> None:
    assert main(["quality", str(SAMPLE)]) == 0
    out = capsys.readouterr().out
    assert "quality: 100/100" in out
    assert "provenance: not evaluated" in out


def test_quality_ros2_qos_reports_real_gaps(capsys) -> None:
    assert main(["quality", str(QOS)]) == 1
    out = capsys.readouterr().out
    assert "lesson_level_short" in out
    assert "L-QOS-002" in out


def test_quality_json(capsys) -> None:
    assert main(["quality", str(FIXTURE), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload["score"], int)
    assert payload["errors"]


def test_quality_auto_reads_draft_metadata(tmp_path: Path, capsys) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(SAMPLE, pack)
    (pack / "draft.json").write_text(
        json.dumps({"searches_per_lesson": 2}), encoding="utf-8"
    )
    research = pack / "research"
    research.mkdir()
    content = load_pack(pack)
    hits = [{"url": resource.url, "trust": "A"} for resource in content.resources.values()]
    for lesson in content.lessons_in_order():
        (research / f"{lesson.manifest.id}.json").write_text(
            json.dumps({
                "lesson_id": lesson.manifest.id,
                "queries": ["q", "q2"],
                "hits": hits,
            }),
            encoding="utf-8",
        )

    assert main(["quality", str(pack)]) == 0
    out = capsys.readouterr().out
    assert "provenance: evaluated" in out
    assert "research: evaluated" in out


def test_quality_explicit_missing_research_dir_is_error(tmp_path: Path, capsys) -> None:
    assert main([
        "quality", str(SAMPLE), "--research-dir", str(tmp_path / "nope"),
    ]) == 2
    assert "not found" in capsys.readouterr().out
