from testbridge.contract.sanitize import find_forbidden_html, sanitize_fragment


def test_strips_script() -> None:
    result = sanitize_fragment('<script>alert(1)</script><p>ok</p>')
    assert "<script" not in result
    assert "<p>ok</p>" in result


def test_strips_event_handlers() -> None:
    result = sanitize_fragment('<p onclick="alert(1)">hi</p>')
    assert "onclick" not in result
    assert ">hi</p>" in result


def test_strips_iframe() -> None:
    result = sanitize_fragment('<iframe src="https://evil.test"></iframe><p>ok</p>')
    assert "<iframe" not in result
    assert "<p>ok</p>" in result


def test_keeps_tb_data_attributes() -> None:
    result = sanitize_fragment('<div data-tb-exercise="EX-ONE"></div>')
    assert 'data-tb-exercise="EX-ONE"' in result


def test_link_gets_rel() -> None:
    result = sanitize_fragment('<a href="https://example.com">x</a>')
    assert 'rel="noopener noreferrer"' in result


def test_find_forbidden_html() -> None:
    issues = find_forbidden_html('<script>x</script><p onclick="x">y</p>')
    assert any("script" in issue for issue in issues)
    assert any("onclick" in issue for issue in issues)
