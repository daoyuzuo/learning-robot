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


def test_find_forbidden_html_flags_style_tag() -> None:
    issues = find_forbidden_html("<style>body{}</style>")
    assert any("style" in issue for issue in issues)


def test_find_forbidden_html_flags_meta_refresh() -> None:
    issues = find_forbidden_html('<meta http-equiv="refresh" content="0">')
    assert any("meta" in issue for issue in issues)


def test_find_forbidden_html_flags_javascript_url() -> None:
    issues = find_forbidden_html('<a href="javascript:alert(1)">x</a>')
    assert any("javascript" in issue for issue in issues)


def test_find_forbidden_html_flags_slash_form_event_handler() -> None:
    issues = find_forbidden_html('<svg onload="alert(1)"></svg>')
    assert any("onload" in issue for issue in issues)


def test_find_forbidden_html_flags_data_url() -> None:
    issues = find_forbidden_html('<a href="data:text/html,x">x</a>')
    assert any("data" in issue for issue in issues)


def test_find_forbidden_html_flags_backslash_rooted_url() -> None:
    assert find_forbidden_html(r'<img src="\evil.com" alt="x">')
    assert find_forbidden_html(r'<img src="\\evil.com/x.png" alt="x">')
    assert find_forbidden_html(r'<img src="\/evil.com/x.png" alt="x">')
    assert find_forbidden_html(r'<a href="/\evil.com/x">x</a>')


def test_find_forbidden_html_flags_protocol_relative_url() -> None:
    assert find_forbidden_html('<a href="//evil.com/x">x</a>')
    assert find_forbidden_html('<img src="//evil.com/x.png" alt="x">')


def test_find_forbidden_html_allows_relative_url() -> None:
    assert find_forbidden_html('<img src="images/x.png" alt="x">') == []
    assert find_forbidden_html(r'<img src="images\x.png" alt="x">') == []
    assert find_forbidden_html('<a href="#section">x</a>') == []


def test_keeps_svg_group_transform() -> None:
    result = sanitize_fragment(
        '<svg><g transform="translate(1,2)"><path d="M0 0"/></g></svg>'
    )
    assert 'transform="translate(1,2)"' in result


def test_svg_group_drops_style_and_event_handlers() -> None:
    result = sanitize_fragment('<svg><g style="fill:red" onmouseover="alert(1)"></g></svg>')
    assert "<g" in result
    assert "style" not in result
    assert "onmouseover" not in result


def test_find_forbidden_html_ignores_text_content() -> None:
    issues = find_forbidden_html('<p>Set style="x" and onclick= handlers in code.</p>')
    assert issues == []


def test_find_forbidden_html_flags_obfuscated_javascript_urls() -> None:
    assert find_forbidden_html("<a href=javascript:alert(1)>x</a>")
    assert find_forbidden_html('<a href="java&#115;cript:alert(1)">x</a>')


def test_svg_accessibility_attributes_survive() -> None:
    html = (
        '<figure class="tb-figure"><svg viewBox="0 0 10 10" role="img" '
        'aria-label="图"><title>标题</title><desc>说明</desc>'
        '<text x="1" y="2" font-weight="600" fill-opacity="0.5">字</text>'
        "</svg><figcaption>说明</figcaption></figure>"
    )
    clean = sanitize_fragment(html)
    assert "<title>标题</title>" in clean
    assert "<desc>说明</desc>" in clean
    assert 'role="img"' in clean
    assert 'aria-label="图"' in clean
    assert 'font-weight="600"' in clean
    assert 'fill-opacity="0.5"' in clean


def test_svg_still_drops_scripts_and_styles() -> None:
    html = '<svg onload="x()" style="color:red"><script>1</script></svg>'
    clean = sanitize_fragment(html)
    assert "onload" not in clean
    assert "style=" not in clean
    assert "<script" not in clean
