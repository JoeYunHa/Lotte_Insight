from fastapi import APIRouter, HTTPException
from datetime import date

from core.database import supabase

router = APIRouter()


# ── 팀 리포트 ─────────────────────────────────────────────────────────────────

@router.get("/team")
def list_team_reports(limit: int = 30):
    result = (
        supabase.table("team_daily_report")
        .select("*")
        .order("date", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


@router.get("/team/{report_date}")
def get_team_report(report_date: date):
    result = (
        supabase.table("team_daily_report")
        .select("*")
        .eq("date", report_date.isoformat())
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="해당 날짜의 팀 리포트가 없습니다.")
    return result.data


# ── 선수 리포트 ───────────────────────────────────────────────────────────────

@router.get("/players/{player_id}")
def list_player_reports(player_id: int, limit: int = 30):
    result = (
        supabase.table("player_daily_report")
        .select("*")
        .eq("player_id", player_id)
        .order("date", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


@router.get("/players/{player_id}/{report_date}")
def get_player_report(player_id: int, report_date: date):
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
    return result.data
