from datetime import date

from fastapi import APIRouter, HTTPException

from core import cache
from core.config import settings
from core.database import supabase

router = APIRouter()


# ── 팀 리포트 ─────────────────────────────────────────────────────────────────

@router.get("/team")
def list_team_reports(limit: int = settings.report_list_limit):
    cache_key = f"report:team:list:{limit}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    result = (
        supabase.table("team_daily_report")
        .select("*")
        .order("date", desc=True)
        .limit(limit)
        .execute()
    )
    data = result.data
    cache.set_json(cache_key, data, cache.ttl_seconds(date.today()))
    return data


@router.get("/team/{report_date}")
def get_team_report(report_date: date):
    cache_key = f"report:team:{report_date.isoformat()}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    result = (
        supabase.table("team_daily_report")
        .select("*")
        .eq("date", report_date.isoformat())
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="해당 날짜의 팀 리포트가 없습니다.")

    data = result.data
    cache.set_json(cache_key, data, cache.ttl_seconds(report_date))
    return data


# ── 선수 리포트 ───────────────────────────────────────────────────────────────

@router.get("/players/{player_id}")
def list_player_reports(player_id: int, limit: int = settings.report_list_limit):
    cache_key = f"report:player:{player_id}:list:{limit}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    result = (
        supabase.table("player_daily_report")
        .select("*")
        .eq("player_id", player_id)
        .order("date", desc=True)
        .limit(limit)
        .execute()
    )
    data = result.data
    cache.set_json(cache_key, data, cache.ttl_seconds(date.today()))
    return data


@router.get("/players/{player_id}/{report_date}")
def get_player_report(player_id: int, report_date: date):
    cache_key = f"report:player:{player_id}:{report_date.isoformat()}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    result = (
        supabase.table("player_daily_report")
        .select("*")
        .eq("player_id", player_id)
        .eq("date", report_date.isoformat())
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="해당 날짜의 선수 리포트가 없습니다.")

    data = result.data
    cache.set_json(cache_key, data, cache.ttl_seconds(report_date))
    return data
