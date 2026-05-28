from datetime import date
from unittest.mock import patch

from batch import fan_voice_review_generator


def test_run_uses_today_or_latest_when_date_not_provided():
    with patch(
        "batch.fan_voice_review_generator.fan_voice_review_service.generate_daily_review",
        return_value={"review_id": 1},
    ) as mock_generate:
        result = fan_voice_review_generator.run([])

    assert result["review_id"] == 1
    kwargs = mock_generate.call_args.kwargs
    assert kwargs["scope"] == "today_or_latest"
    assert kwargs["requested_date"] is None


def test_run_uses_date_scope_when_date_provided():
    with patch(
        "batch.fan_voice_review_generator.fan_voice_review_service.generate_daily_review",
        return_value={"review_id": 2},
    ) as mock_generate:
        result = fan_voice_review_generator.run(["--date", "2026-05-28", "--review-type", "interim"])

    assert result["review_id"] == 2
    kwargs = mock_generate.call_args.kwargs
    assert kwargs["scope"] == "date"
    assert kwargs["requested_date"] == date(2026, 5, 28)
    assert kwargs["review_type"] == "interim"
