from pathlib import Path

from testbridge.cli import main
from testbridge.studio.verify import ResourceCheck

FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "minimal-pack"


def fake_check(ok: bool):
    def check_url(client, url):
        return ResourceCheck(url, 200 if ok else 404, url, 100, False, "")
    return check_url


def test_verify_resources_ok(monkeypatch, capsys) -> None:
    monkeypatch.setattr("testbridge.cli.check_url", fake_check(True))
    monkeypatch.setattr(
        "testbridge.cli.httpx.Client",
        lambda **kwargs: type("C", (), {"close": lambda self: None})(),
    )

    code = main(["verify-resources", str(FIXTURE)])

    out = capsys.readouterr().out
    assert code == 0
    assert "DOC-ONE" in out
    assert "OK" in out


def test_verify_resources_failure_is_nonzero(monkeypatch, capsys) -> None:
    monkeypatch.setattr("testbridge.cli.check_url", fake_check(False))
    monkeypatch.setattr(
        "testbridge.cli.httpx.Client",
        lambda **kwargs: type("C", (), {"close": lambda self: None})(),
    )

    code = main(["verify-resources", str(FIXTURE)])

    out = capsys.readouterr().out
    assert code == 1
    assert "DOC-ONE" in out
    assert "HTTP 404" in out


def test_verify_resources_invalid_pack(monkeypatch, capsys) -> None:
    code = main(["verify-resources", "does-not-exist"])

    assert code == 2
    assert "ERROR" in capsys.readouterr().err
