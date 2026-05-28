from __future__ import annotations

import re
from html import unescape

_PROFANITY_WORDS = {
    "fuck",
    "shit",
    "bitch",
}

_URL_RE = re.compile(r"https?://|www\.|\.com|\.net|\.kr", re.IGNORECASE)
_PHONE_RE = re.compile(r"01[0-9]-?\d{3,4}-?\d{4}")
_REPEATED_CHAR_RE = re.compile(r"(.)\1{5,}")
_TAG_RE = re.compile(r"<[^>]+>")


def normalize_message(text: str) -> str:
    cleaned = unescape(text or "")
    cleaned = _TAG_RE.sub(" ", cleaned)
    cleaned = cleaned.replace("<", " ").replace(">", " ")
    return " ".join(cleaned.strip().split())


def validate_message(text: str) -> None:
    if not text:
        raise ValueError("message is empty")
    if len(text) > 60:
        raise ValueError("message too long")
    if _contains_url(text):
        raise ValueError("url is not allowed")
    if _contains_phone(text):
        raise ValueError("phone is not allowed")
    if _contains_repeated_chars(text):
        raise ValueError("repeated characters are not allowed")
    if _contains_profanity(text):
        raise ValueError("profanity is not allowed")


def _contains_url(text: str) -> bool:
    return _URL_RE.search(text) is not None


def _contains_phone(text: str) -> bool:
    return _PHONE_RE.search(text) is not None


def _contains_repeated_chars(text: str) -> bool:
    return _REPEATED_CHAR_RE.search(text) is not None


def _contains_profanity(text: str) -> bool:
    low = text.lower()
    return any(word in low for word in _PROFANITY_WORDS)
