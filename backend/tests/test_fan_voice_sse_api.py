import asyncio
import json
from unittest.mock import patch

from api.fan_voice import generate_stream_sse_events


class _ConnectedRequest:
    async def is_disconnected(self) -> bool:
        return False


async def _read_first_event(*, context_type: str = "home", context_id: str = "today") -> str:
    gen = generate_stream_sse_events(
        request=_ConnectedRequest(),
        context_type=context_type,
        context_id=context_id,
        limit=30,
    )
    return await anext(gen)


def test_sse_stream_emits_stream_event_with_slow_mode_payload():
    payload = {
        "messages": [{"id": "m1", "message": "hello"}],
        "slow_mode": True,
        "next_poll_after_ms": 5000,
    }
    with patch("api.fan_voice.fan_voice_service.get_stream", return_value=payload):
        chunk = asyncio.run(_read_first_event())

    assert "event: stream" in chunk
    assert "data:" in chunk
    body = chunk.split("data: ", 1)[1].strip()
    parsed = json.loads(body)
    assert parsed["slow_mode"] is True
    assert parsed["messages"][0]["id"] == "m1"


def test_sse_stream_can_be_reconnected_by_repeating_connection():
    payload = {"messages": [], "slow_mode": False, "next_poll_after_ms": 5000}
    with patch("api.fan_voice.fan_voice_service.get_stream", return_value=payload):
        first = asyncio.run(_read_first_event())
        second = asyncio.run(_read_first_event())

    assert "event: stream" in first
    assert "event: stream" in second
