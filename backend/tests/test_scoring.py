from app.services.scoring import parse_llm_response, score_open_answer


def test_parse_valid_json():
    raw = '{"score": 4, "reason": "Uses AI weekly and edits replies.", "flags": ["unreviewed_output"]}'
    res = parse_llm_response(raw)
    assert res["score"] == 4.0
    assert res["reason"] == "Uses AI weekly and edits replies."
    assert res["flags"] == ["unreviewed_output"]


def test_parse_markdown_fenced_json():
    raw = '```json\n{"score": 3, "reason": "Regular summarization.", "flags": []}\n```'
    res = parse_llm_response(raw)
    assert res["score"] == 3.0
    assert res["reason"] == "Regular summarization."
    assert res["flags"] == []


def test_parse_fenced_without_language_specifier():
    raw = '```\n{"score": 5, "reason": "Advanced reusable workflows.", "flags": []}\n```'
    res = parse_llm_response(raw)
    assert res["score"] == 5.0
    assert res["reason"] == "Advanced reusable workflows."


def test_parse_score_clamping():
    # Out-of-bounds high score clamped to 5.0
    high = parse_llm_response('{"score": 10, "reason": "Exceeds scale.", "flags": []}')
    assert high["score"] == 5.0

    # Out-of-bounds low score clamped to 1.0
    low = parse_llm_response('{"score": -2, "reason": "Negative.", "flags": []}')
    assert low["score"] == 1.0


def test_parse_word_score():
    res = parse_llm_response('{"score": "four", "reason": "Word score.", "flags": []}')
    assert res["score"] == 4.0


def test_parse_missing_reason_fallback():
    res = parse_llm_response('{"score": 3, "flags": ["unreviewed_output"]}')
    assert res["score"] == 3.0
    assert res["reason"] == "No specific reason provided."
    assert res["flags"] == ["unreviewed_output"]


def test_parse_filters_invalid_flags():
    res = parse_llm_response(
        '{"score": 2, "reason": "Dubious claims.", "flags": ["customer_data_shared", "made_up_flag", "probably_lying"]}'
    )
    assert res["score"] == 2.0
    # Only valid rubric flags are retained
    assert res["flags"] == ["customer_data_shared"]


def test_parse_malformed_json_fallback():
    res = parse_llm_response("This is not JSON at all.")
    assert res["score"] == 1.0
    assert "Unable to evaluate" in res["reason"]
    assert res["flags"] == []


def test_parse_empty_and_non_string():
    assert parse_llm_response("")["score"] == 1.0
    assert parse_llm_response(None)["score"] == 1.0


def test_score_open_answer_mock_integration():
    # score_open_answer uses mock responses deterministically based on md5 hash
    res = score_open_answer("How do you use AI?", "I used ChatGPT to draft 20 follow-up emails.")
    assert isinstance(res["score"], float)
    assert 1.0 <= res["score"] <= 5.0
    assert isinstance(res["reason"], str)
    assert isinstance(res["flags"], list)

