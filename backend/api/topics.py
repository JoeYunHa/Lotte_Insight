from datetime import date

from fastapi import APIRouter, HTTPException, Query

from core.time_utils import today_kst
from services.topic_repository import get_topic_map

router = APIRouter()


@router.get("")
def get_topic_map_endpoint(map_date: date | None = Query(default=None)):
    target = map_date if map_date is not None else today_kst()
    data = get_topic_map(target)
    if data is None:
        raise HTTPException(status_code=404, detail="topic map not found for this date")
    return data
