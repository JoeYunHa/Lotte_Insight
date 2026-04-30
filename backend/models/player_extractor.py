from services.player_catalog import invalidate_cache, list_players


def extract_players(title: str) -> list[int]:
    """Return player IDs whose name or variant appears in the article title."""
    found: list[int] = []
    for player in list_players():
        names = [player["name"]] + (player.get("name_variants") or [])
        if any(name in title for name in names):
            found.append(player["id"])
    return found
