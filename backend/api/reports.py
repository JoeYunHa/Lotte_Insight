from datetime import date

from fastapi import APIRouter, HTTPException, Query

from core.config import settings
from services import report_service

router = APIRouter()


@router.get("/team")
def list_team_reports(limit: int = Query(default=settings.report_list_limit, ge=1, le=200)):
    return report_service.list_team_reports(limit)


@router.get("/team/{report_date}")
def get_team_report(report_date: date):
    report = report_service.get_team_report(report_date)
    if not report:
        raise HTTPException(status_code=404, detail="해당 날짜의 팀 리포트가 없습니다.")
    return report


@router.get("/players/{player_id}")
def list_player_reports(player_id: int, limit: int = Query(default=settings.report_list_limit, ge=1, le=200)):
    return report_service.list_player_reports(player_id, limit)


@router.get("/players/{player_id}/{report_date}")
def get_player_report(player_id: int, report_date: date):
    report = report_service.get_player_report(player_id, report_date)
    if not report:
        raise HTTPException(status_code=404, detail="해당 날짜의 선수 리포트가 없습니다.")
    return report
