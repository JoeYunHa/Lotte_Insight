from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services import fan_voice_review_service

router = APIRouter()


def _resolve_date_or_400(scope: str, requested_date: date | None):
    try:
        return fan_voice_review_service.resolve_target_game_date(
            scope=scope, requested_date=requested_date
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class ReviewGenerationOptions(BaseModel):
    clustering_algorithm: str = "jaccard_trigram_v1"
    min_cluster_size: int = Field(default=2, ge=1, le=50)
    similarity_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    max_opinions: int = Field(default=5, ge=1, le=20)
    use_llm_summary: bool = False


class ReviewGenerateRequest(BaseModel):
    target_date: date | None = None
    context_type: str = "home"
    context_id: str = "today"
    review_type: str = "final"
    force: bool = False
    generation_options: ReviewGenerationOptions | None = None


@router.get("/opinion-review")
def get_opinion_review(
    scope: str = Query(default="today_or_latest"),
    report_date: date | None = Query(default=None, alias="date"),
    context_type: str = Query(default="home"),
    context_id: str = Query(default="today"),
    review_type: str = Query(default="latest"),
):
    """
    Get daily opinion review.
    Date resolution is delegated to service layer (no duplication).
    """
    try:
        result = fan_voice_review_service.get_daily_review(
            scope=scope,
            requested_date=report_date,
            context_type=context_type,
            context_id=context_id,
            review_type="final" if review_type == "latest" else review_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="review not found")
    return result


@router.get("/emotions/ranking")
def get_emotion_ranking(
    scope: str = Query(default="today_or_latest"),
    report_date: date | None = Query(default=None, alias="date"),
    context_type: str = Query(default="home"),
    context_id: str = Query(default="today"),
    limit: int = Query(default=5, ge=1, le=20),
    min_mentions: int = Query(default=0, ge=0, le=10000),
):
    try:
        return fan_voice_review_service.get_emotion_ranking(
            scope=scope,
            requested_date=report_date,
            context_type=context_type,
            context_id=context_id,
            min_mentions=min_mentions,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/players/ranking")
def get_player_ranking(
    scope: str = Query(default="today_or_latest"),
    report_date: date | None = Query(default=None, alias="date"),
    context_type: str = Query(default="home"),
    context_id: str = Query(default="today"),
    limit: int = Query(default=10, ge=1, le=50),
    min_mentions: int = Query(default=0, ge=0, le=10000),
    sentiment_filter: str | None = Query(default=None),
):
    try:
        return fan_voice_review_service.get_player_ranking(
            scope=scope,
            requested_date=report_date,
            context_type=context_type,
            context_id=context_id,
            min_mentions=min_mentions,
            limit=limit,
            sentiment_filter=sentiment_filter,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/opinion-review/generate")
def generate_opinion_review(payload: ReviewGenerateRequest):
    try:
        return fan_voice_review_service.generate_daily_review(
            scope="date" if payload.target_date else "today_or_latest",
            requested_date=payload.target_date,
            context_type=payload.context_type,
            context_id=payload.context_id,
            review_type=payload.review_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
