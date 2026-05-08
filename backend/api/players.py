from datetime import date

from fastapi import APIRouter, HTTPException

from services.player_repository import (
    get_player as get_player_record,
    list_players as list_player_records,
)

router = APIRouter()


@router.get("/")
def list_players(status: str | None = None):
    return list_player_records(status=status)


@router.get("/{player_id}")
def get_player(player_id: int, stats_date: date | None = None):
    player = get_player_record(player_id, stats_date=stats_date)
    if not player:
        raise HTTPException(status_code=404, detail="선수를 찾을 수 없습니다.")
    return player
