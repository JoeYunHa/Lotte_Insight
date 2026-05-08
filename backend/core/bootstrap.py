from types import SimpleNamespace
import os


def load_settings():
    try:
        from core.config import settings as app_settings

        return app_settings
    except ModuleNotFoundError:
        pass

    try:
        from backend.core.config import settings as app_settings

        return app_settings
    except ModuleNotFoundError:
        pass

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
