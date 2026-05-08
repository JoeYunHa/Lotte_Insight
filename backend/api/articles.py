from datetime import date

from fastapi import APIRouter, HTTPException, Query

from services.article_repository import (
    get_article as get_article_record,
    list_articles as list_article_records,
)

router = APIRouter()


@router.get("/")
def list_articles(
    article_date: date | None = None,
    label: str | None = None,
    player_id: int | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
):
    return list_article_records(
        article_date=article_date,
        label=label,
        player_id=player_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{article_id}")
def get_article(article_id: int):
    article = get_article_record(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
    return article
