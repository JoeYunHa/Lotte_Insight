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

    upserted = 0
    for name in roster_names:
        if name in existing_by_name:
            player = existing_by_name[name]
            if player.get("status") != "active":
                supabase.table("players").update({"status": "active"}).eq("id", player["id"]).execute()
                logger.info("Reactivated player: %s", name)
        else:
            supabase.table("players").insert(
                {"name": name, "name_variants": [], "status": "active"}
            ).execute()
            logger.info("Added new player: %s", name)
        upserted += 1

    deactivated = 0
    for name, player in existing_by_name.items():
        if name not in roster_set and player.get("status") not in ("inactive", None):
            supabase.table("players").update({"status": "inactive"}).eq("id", player["id"]).execute()
            logger.info("Deactivated player: %s", name)
            deactivated += 1

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
