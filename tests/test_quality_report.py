from testbridge.quality.report import (
    QualityIssue,
    QualityMetric,
    QualityReport,
    build_report,
    proportional,
    round_half_up,
)


def test_round_half_up() -> None:
    assert round_half_up(3.5) == 4
    assert round_half_up(3.49) == 3


def test_proportional() -> None:
    assert proportional(0, 4, 10) == 0
    assert proportional(2, 4, 10) == 5
    assert proportional(1, 3, 5) == 2
    assert proportional(0, 0, 10) == 0


def test_build_report_normalizes_and_sorts() -> None:
    report = build_report(
        [QualityMetric("a", "A", 10, 15, ""), QualityMetric("b", "B", 5, 5, "")],
        [QualityIssue("z", "z", "error"), QualityIssue("a", "a", "error")],
        [QualityIssue("w", "w", "warning")],
        provenance_evaluated=False,
        research_evaluated=False,
    )

    assert report.earned == 15
    assert report.possible == 20
    assert report.score == 75
    assert report.ok is False
    assert [issue.code for issue in report.errors] == ["a", "z"]


def test_report_as_dict_and_ok() -> None:
    report = QualityReport(score=100)
    assert report.ok is True
    data = report.as_dict()
    assert data["score"] == 100
    assert data["metrics"] == []
    assert data["ok"] is True
