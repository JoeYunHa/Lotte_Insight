import os
from types import SimpleNamespace


def _try_import_settings(module_path: str):
    module = __import__(module_path, fromlist=["settings"])
    return module.settings


def load_settings():
    for module_path in ("core.config", "backend.core.config"):
        try:
            return _try_import_settings(module_path)
        except ModuleNotFoundError:
            continue

    return SimpleNamespace(
        crawl_user_agent=os.getenv("CRAWL_USER_AGENT", "LotteInsightBot/1.0"),
        team_code=os.getenv("TEAM_CODE", "LT"),
        team_name_ko=os.getenv("TEAM_NAME_KO", "롯데"),
    )


def load_supabase():
    try:
        from core.database import supabase

        return supabase
    except ModuleNotFoundError:
        from backend.core.database import supabase

        return supabase


def load_player_name_to_id_map() -> dict:
    try:
        from services.player_catalog import player_name_to_id_map
    except ModuleNotFoundError:
        from backend.services.player_catalog import player_name_to_id_map

    return player_name_to_id_map()
