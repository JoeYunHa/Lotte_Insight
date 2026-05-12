from services.player_catalog import build_player_alias_index


def extract_players(title: str) -> list[int]:
    """Return player IDs whose name or variant appears in the article title."""
    return build_player_alias_index().match_player_ids(title)
