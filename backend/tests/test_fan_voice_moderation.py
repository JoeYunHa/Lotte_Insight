import pytest

from services.fan_voice_moderation import normalize_message, validate_message


def test_normalize_message_collapses_spaces():
    assert normalize_message("  hello   world  ") == "hello world"


@pytest.mark.parametrize(
    "text",
    [
        "visit https://example.com",
        "call me 010-1234-5678",
        "aaaaaa",
        "this is shit",
    ],
)
def test_validate_message_rejects_bad_text(text: str):
    with pytest.raises(ValueError):
        validate_message(text)


def test_validate_message_accepts_safe_text():
    validate_message("Go giants tonight")
