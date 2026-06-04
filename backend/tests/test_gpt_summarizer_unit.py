from __future__ import annotations

import sys
from pathlib import Path

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
