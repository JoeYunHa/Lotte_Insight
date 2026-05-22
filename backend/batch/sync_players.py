"""
Sync the players table with the current KBO 1-gun register roster.

Run once at season start, and again whenever the roster changes significantly.
After this runs, players on the current register have status="active" and
departed players have status="inactive".
"""

import logging

try:
    from core.bootstrap import load_supabase
    from batch.kbo_crawler import fetch_roster
    from services.player_catalog import invalidate_cache, list_players
except ModuleNotFoundError:
    from backend.core.bootstrap import load_supabase
    from backend.batch.kbo_crawler import fetch_roster
    from backend.services.player_catalog import invalidate_cache, list_players

logger = logging.getLogger(__name__)


def run() -> dict:
    logger.info("Player roster sync started")
    supabase = load_supabase()

    roster_names = fetch_roster()
    if not roster_names:
        logger.warning("fetch_roster() returned empty list; aborting sync")
        return {"upserted": 0, "deactivated": 0}

    logger.info("Fetched %d players from KBO register", len(roster_names))
    roster_set = set(roster_names)

    existing = list_players(use_cache=False)
    existing_by_name: dict[str, dict] = {p["name"]: p for p in existing}

    new_names: list[str] = []
    reactivate_ids: list[int] = []
    for name in roster_names:
        if name in existing_by_name:
            if existing_by_name[name].get("status") != "active":
                reactivate_ids.append(existing_by_name[name]["id"])
        else:
            new_names.append(name)

    if new_names:
        supabase.table("players").insert(
            [{"name": n, "name_variants": [], "status": "active"} for n in new_names]
        ).execute()
        logger.info("Added %d new players: %s", len(new_names), new_names)

    if reactivate_ids:
        supabase.table("players").update({"status": "active"}).in_("id", reactivate_ids).execute()
        logger.info("Reactivated %d players", len(reactivate_ids))

    upserted = len(new_names) + len(reactivate_ids)

    deactivate_ids = [
        player["id"]
        for name, player in existing_by_name.items()
        if name not in roster_set and player.get("status") not in ("inactive", None)
    ]
    if deactivate_ids:
        supabase.table("players").update({"status": "inactive"}).in_("id", deactivate_ids).execute()
        logger.info("Deactivated %d players", len(deactivate_ids))
    deactivated = len(deactivate_ids)

    invalidate_cache()

    result = {"upserted": upserted, "deactivated": deactivated}
    logger.info("Player roster sync completed: %s", result)
    return result


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    result = run()
    print(result)
    sys.exit(0)
