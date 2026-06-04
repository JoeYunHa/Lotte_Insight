from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def test_parse_label_response_normalizes_valid_output():
    from batch.gpt_summarizer import _parse_label_response

    parsed = _parse_label_response(
        '{"label":"match_related","confidence":0.87,"secondary_labels":["INTERVIEW","UNKNOWN"]}'
    )

    assert parsed == {
        "label": "MATCH_RELATED",
        "confidence": 0.87,
        "secondary_labels": ["INTERVIEW"],
        "source": "gpt",
    }


def test_parse_label_response_falls_back_to_etc_on_invalid_json():
    from batch.gpt_summarizer import _parse_label_response

    parsed = _parse_label_response("not json")

    assert parsed["label"] == "ETC"
    assert parsed["confidence"] == 0.0
    assert parsed["secondary_labels"] == []
    assert parsed["source"] == "gpt_error"


def test_call_gpt_label_returns_cache_hit_without_calling_openai():
    from batch.gpt_summarizer import _call_gpt_label

    cached_result = {"label": "MATCH_RELATED", "confidence": 0.9, "secondary_labels": [], "source": "gpt"}

    with patch("batch.gpt_summarizer.cache.get_json", return_value=cached_result) as mock_get, \
         patch("batch.gpt_summarizer._get_client") as mock_client:
        result = _call_gpt_label("롯데 승리", "경기 결과 스냅샷")

    assert result == cached_result
    mock_get.assert_called_once()
    mock_client.assert_not_called()


def test_call_gpt_label_returns_label_error_on_api_exception():
    import openai
    from batch.gpt_summarizer import _call_gpt_label, _LABEL_ERROR

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = openai.APIConnectionError(request=MagicMock())

    with patch("batch.gpt_summarizer.cache.get_json", return_value=None), \
         patch("batch.gpt_summarizer._get_client", return_value=mock_client), \
         patch("batch.gpt_summarizer.settings", SimpleNamespace(openai_model="gpt-4o-mini")), \
         patch("batch.gpt_summarizer.cache.set_json") as mock_set:
        result = _call_gpt_label("롯데 부상 소식", "선수 부상 세부 정보")

    assert result["label"] == _LABEL_ERROR["label"]
    assert result["source"] == "gpt_error"
    mock_set.assert_not_called()


def test_call_gpt_label_does_not_cache_gpt_error_result():
    from batch.gpt_summarizer import _call_gpt_label

    mock_client = MagicMock()
    bad_response = MagicMock()
    bad_response.choices[0].message.content = "not valid json {"
    mock_client.chat.completions.create.return_value = bad_response

    with patch("batch.gpt_summarizer.cache.get_json", return_value=None), \
         patch("batch.gpt_summarizer._get_client", return_value=mock_client), \
         patch("batch.gpt_summarizer.settings", SimpleNamespace(openai_model="gpt-4o-mini")), \
         patch("batch.gpt_summarizer.cache.set_json") as mock_set:
        result = _call_gpt_label("제목", "스니펫")

    assert result["source"] == "gpt_error"
    mock_set.assert_not_called()
