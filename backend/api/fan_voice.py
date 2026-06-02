from __future__ import annotations

from datetime import date
import asyncio
import json
import time

from fastapi import APIRouter, Cookie, HTTPException, Query, Response
from fastapi import Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import logging

from services import fan_voice_service
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

_SESSION_COOKIE_NAME = "fan_session"
_SESSION_MAX_AGE_SEC = 60 * 60 * 24 * 30
_SSE_HEARTBEAT_SEC = 15
_SSE_MAX_DURATION_SEC = 60 * 60


class FanVoiceSessionResponse(BaseModel):
    session_alias: str
    slow_mode: bool
    blocked: bool


class FanVoiceMessageCreate(BaseModel):
    context_type: str
    context_id: str
    message: str = Field(min_length=1, max_length=60)
    emotion_tag: str | None = None
    topic_tag: str | None = None
    player_id: int | None = None
    cluster_id: str | None = None
    game_date: date | None = None


class FanVoiceReactionCreate(BaseModel):
    message_id: str
    reaction_type: str


class FanVoiceReportCreate(BaseModel):
    message_id: str
    reason: str


def _raise_http_from_service_error(exc: Exception) -> None:
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


@router.post("/session", response_model=FanVoiceSessionResponse)
def init_session(
    response: Response,
    fan_session: str | None = Cookie(default=None),
):
    token, session = fan_voice_service.init_session(fan_session)
    response.set_cookie(
        key=_SESSION_COOKIE_NAME,
        value=token,
        max_age=_SESSION_MAX_AGE_SEC,
        httponly=True,
        samesite="lax",
        secure=settings.app_env != "development",
    )
    return {
        "session_alias": session["session_alias"],
        "slow_mode": False,
        "blocked": bool(session.get("is_blocked", False)),
    }


@router.get("/stream")
def get_stream(
    context_type: str,
    context_id: str,
    limit: int = Query(default=30, ge=1, le=100),
):
    try:
        return fan_voice_service.get_stream(
            context_type=context_type,
            context_id=context_id,
            limit=limit,
        )
    except Exception as exc:
        _raise_http_from_service_error(exc)


@router.get("/stream/sse")
async def get_stream_sse(
    request: Request,
    context_type: str,
    context_id: str,
    limit: int = Query(default=30, ge=1, le=100),
):
    return StreamingResponse(
        generate_stream_sse_events(
            request=request,
            context_type=context_type,
            context_id=context_id,
            limit=limit,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def generate_stream_sse_events(
    *,
    request: Request,
    context_type: str,
    context_id: str,
    limit: int,
):
    started = time.monotonic()
    consecutive_errors = 0
    while True:
        if await request.is_disconnected():
            break
        if time.monotonic() - started > _SSE_MAX_DURATION_SEC:
            yield "event: timeout\ndata: {}\n\n"
            break
        try:
            payload = await asyncio.to_thread(
                lambda: fan_voice_service.get_stream(
                    context_type=context_type,
                    context_id=context_id,
                    limit=limit,
                )
            )
            consecutive_errors = 0
            data = json.dumps(payload, ensure_ascii=False)
            yield f"event: stream\ndata: {data}\n\n"
            wait_ms = int(payload.get("next_poll_after_ms", 5000))
            wait_sec = max(1, min(60, wait_ms // 1000))
            await asyncio.sleep(wait_sec)
        except PermissionError as exc:
            error_data = json.dumps({"detail": str(exc)}, ensure_ascii=False)
            yield f"event: error\ndata: {error_data}\n\n"
            break
        except ValueError as exc:
            error_data = json.dumps({"detail": str(exc)}, ensure_ascii=False)
            yield f"event: error\ndata: {error_data}\n\n"
            break
        except Exception:
            # Keep the stream alive on transient failures, but abort the
            # connection if errors persist so we don't loop forever.
            consecutive_errors += 1
            logger.exception(
                "SSE stream error (consecutive=%d) context=%s:%s",
                consecutive_errors,
                context_type,
                context_id,
            )
            if consecutive_errors >= 3:
                yield 'event: error\ndata: {"error": "stream_error"}\n\n'
                return
            yield "event: heartbeat\ndata: {}\n\n"
            await asyncio.sleep(_SSE_HEARTBEAT_SEC)


@router.post("/messages")
def create_message(
    payload: FanVoiceMessageCreate,
    fan_session: str | None = Cookie(default=None),
):
    if not fan_session:
        raise HTTPException(status_code=401, detail="missing fan session")
    try:
        created = fan_voice_service.create_message(
            session_token=fan_session,
            context_type=payload.context_type,
            context_id=payload.context_id,
            message=payload.message,
            emotion_tag=payload.emotion_tag,
            topic_tag=payload.topic_tag,
            player_id=payload.player_id,
            cluster_id=payload.cluster_id,
            game_date=payload.game_date.isoformat() if payload.game_date else None,
        )
        return created
    except Exception as exc:
        _raise_http_from_service_error(exc)


@router.post("/reactions")
def create_reaction(
    payload: FanVoiceReactionCreate,
    fan_session: str | None = Cookie(default=None),
):
    if not fan_session:
        raise HTTPException(status_code=401, detail="missing fan session")
    try:
        reaction_count = fan_voice_service.react_message(
            session_token=fan_session,
            message_id=payload.message_id,
            reaction_type=payload.reaction_type,
        )
        return {"ok": True, "reaction_count": reaction_count}
    except Exception as exc:
        _raise_http_from_service_error(exc)


@router.post("/reports")
def create_report(
    payload: FanVoiceReportCreate,
    fan_session: str | None = Cookie(default=None),
):
    if not fan_session:
        raise HTTPException(status_code=401, detail="missing fan session")
    try:
        report_count = fan_voice_service.report_message(
            session_token=fan_session,
            message_id=payload.message_id,
            reason=payload.reason,
        )
        return {"ok": True, "report_count": report_count}
    except Exception as exc:
        _raise_http_from_service_error(exc)
