import json
import sys

import requests

from settings import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_TIMEOUT_SECONDS,
)


def require_openai_api_key() -> None:
    if not OPENAI_API_KEY:
        print("[ERROR] OPENAI_API_KEY 환경변수가 없습니다.")
        sys.exit(1)


def chat_json(
    system_prompt: str,
    user_content: str,
    *,
    max_tokens: int,
    temperature: float = OPENAI_TEMPERATURE,
) -> dict:
    require_openai_api_key()

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        },
        timeout=OPENAI_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return json.loads(response.json()["choices"][0]["message"]["content"])
