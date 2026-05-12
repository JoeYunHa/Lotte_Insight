from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Query

from core import cache
from services import home_service

router = APIRouter()

_KST = timezone(timedelta(hours=9))


def _today_kst() -> date:
    return datetime.now(_KST).date()


@router.get("/home")
def get_home_report(report_date: date | None = Query(default=None)):
    target = report_date or _today_kst()

    cache_key = f"report:home:{target.isoformat()}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    result = home_service.build_home_report(target)
    cache.set_json(cache_key, result, ttl=cache.ttl_seconds(target))
    return result
