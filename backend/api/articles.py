from fastapi import APIRouter, Query, HTTPException
from datetime import date

from core.database import supabase

router = APIRouter()


@router.get("/")
def list_articles(
    article_date: date | None = None,
    label: str | None = None,
    player_id: int | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
):
    query = supabase.table("articles").select(
        "id, source_url, source_name, title, published_at, author_name, "
        "article_labels(label, confidence), "
        "article_players(player_id, players(name))"
    )

    if article_date:
        query = query.gte("published_at", f"{article_date}T00:00:00+00:00").lte(
            "published_at", f"{article_date}T23:59:59+00:00"
        )

    if player_id:
        ap_result = (
            supabase.table("article_players")
            .select("article_id")
            .eq("player_id", player_id)
            .execute()
        )
        article_ids = [r["article_id"] for r in ap_result.data]
        if not article_ids:
            return []
        query = query.in_("id", article_ids)

    if label:
        al_result = (
            supabase.table("article_labels")
            .select("article_id")
            .eq("label", label)
            .execute()
        )
        label_ids = [r["article_id"] for r in al_result.data]
        if not label_ids:
            return []
        query = query.in_("id", label_ids)

    result = query.order("published_at", desc=True).range(offset, offset + limit - 1).execute()
    return result.data


@router.get("/{article_id}")
def get_article(article_id: int):
    result = (
        supabase.table("articles")
        .select("*, article_labels(*), article_players(*, players(*))")
        .eq("id", article_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
    return result.data
