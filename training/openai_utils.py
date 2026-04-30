"""OpenAI API utilities for training data labeling."""

from __future__ import annotations

import sys

from openai import OpenAI

from settings import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_TIMEOUT_SECONDS,
)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY, timeout=OPENAI_TIMEOUT_SECONDS)
    return _client


def require_openai_api_key() -> None:
    if not OPENAI_API_KEY:
        print("[ERROR] OPENAI_API_KEY environment variable is missing.")
        sys.exit(1)


def chat_json(system_prompt: str, user_content: str, max_tokens: int = 500) -> dict:
    """Call OpenAI chat completion and return parsed JSON response."""
    response = _get_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        max_tokens=max_tokens,
        temperature=OPENAI_TEMPERATURE,
        response_format={"type": "json_object"},
    )
    import json
    return json.loads(response.choices[0].message.content)
