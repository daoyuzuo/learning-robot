from testbridge.tutor.parse import parse_answer

HEADINGS = ["六类策略", "兼容性：Request vs Offered"]
RESOURCES = ["DOC-QOS-SETTINGS"]


def test_parses_valid_json() -> None:
    raw = (
        '{"answer": "因为发布端只保证 best effort。", "basis": "lesson", '
        '"citations": ["六类策略"], "followups": ["要不要看实例？"]}'
    )
    result = parse_answer(raw, headings=HEADINGS, resource_ids=RESOURCES)
    assert result.answer == "因为发布端只保证 best effort。"
    assert result.basis == "lesson"
    assert result.citations == ["六类策略"]
    assert result.followups == ["要不要看实例？"]


def test_invalid_json_falls_back_to_general() -> None:
    result = parse_answer("这不是 JSON", headings=HEADINGS, resource_ids=RESOURCES)
    assert result.answer == "这不是 JSON"
    assert result.basis == "general"
    assert result.citations == []
    assert result.followups == []


def test_unknown_basis_becomes_general() -> None:
    result = parse_answer(
        '{"answer": "x", "basis": "guess"}', headings=HEADINGS, resource_ids=RESOURCES
    )
    assert result.basis == "general"


def test_invented_citations_are_dropped() -> None:
    raw = (
        '{"answer": "x", "basis": "resource", '
        '"citations": ["DOC-QOS-SETTINGS", "DOC-FAKE"]}'
    )
    result = parse_answer(raw, headings=HEADINGS, resource_ids=RESOURCES)
    assert result.citations == ["DOC-QOS-SETTINGS"]


def test_code_fences_are_tolerated() -> None:
    raw = '```json\n{"answer": "x", "basis": "general"}\n```'
    assert parse_answer(raw, headings=HEADINGS, resource_ids=RESOURCES).answer == "x"


def test_followups_are_limited_to_three() -> None:
    raw = '{"answer": "x", "followups": ["a", "b", "c", "d"]}'
    result = parse_answer(raw, headings=HEADINGS, resource_ids=RESOURCES)
    assert result.followups == ["a", "b", "c"]


def test_long_answers_are_truncated() -> None:
    raw = '{"answer": "' + "字" * 9000 + '"}'
    result = parse_answer(raw, headings=HEADINGS, resource_ids=RESOURCES)
    assert result.answer.endswith("（已截断）")
    assert len(result.answer) <= 8010
