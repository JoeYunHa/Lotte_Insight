#!/usr/bin/env python3
"""
Validate Supabase runtime setup before deployment.

Checks:
- required environment variables
- service role key shape
- required tables
- RLS policies (via exec_sql RPC)
- required indexes (via exec_sql RPC)
- required RPC functions
"""

import logging
import sys
from pathlib import Path
from typing import List, Tuple

# Ensure backend package import works from both invocation paths.
current_file = Path(__file__).resolve()
backend_dir = current_file.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.config import settings
from core.database import supabase

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_TABLES = [
    "players",
    "games",
    "articles",
    "article_labels",
    "article_players",
    "player_stats_daily",
    "team_daily_report",
    "player_daily_report",
    "topic_clusters",
    "article_topic_points",
]

REQUIRED_POLICIES = {
    "players": "players_read_public",
    "games": "games_read_public",
    "articles": "articles_read_public",
    "article_labels": "article_labels_read_public",
    "article_players": "article_players_read_public",
    "player_stats_daily": "player_stats_daily_read_public",
    "team_daily_report": "team_daily_report_read_public",
    "player_daily_report": "player_daily_report_read_public",
    "topic_clusters": "topic_clusters_read_public",
    "article_topic_points": "article_topic_points_read_public",
}

REQUIRED_INDEXES = [
    ("articles", "idx_articles_published_at"),
    ("article_labels", "idx_article_labels_article_id"),
    ("article_players", "idx_article_players_player_id"),
    ("topic_clusters", "topic_clusters_map_date_idx"),
    ("article_topic_points", "article_topic_points_map_date_idx"),
]

REQUIRED_FUNCTIONS = ["replace_topic_map"]

REQUIRED_ENV_VARS = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "NAVER_CLIENT_ID",
    "NAVER_CLIENT_SECRET",
    "OPENAI_API_KEY",
]


def _exec_catalog_query(query: str) -> list[dict]:
    """Run catalog query via exec_sql RPC and fail hard if unavailable."""
    result = supabase.rpc("exec_sql", {"query": query}).execute()
    return result.data or []


def check_tables() -> Tuple[bool, List[str]]:
    logger.info("Checking required tables...")
    missing: List[str] = []
    for table_name in REQUIRED_TABLES:
        try:
            supabase.table(table_name).select("*").limit(1).execute()
            logger.info("  OK %s", table_name)
        except Exception as exc:
            logger.error("  FAIL %s: %s", table_name, exc)
            missing.append(table_name)
    return len(missing) == 0, missing


def check_rls_policies() -> Tuple[bool, List[str]]:
    logger.info("Checking RLS policies...")
    missing: List[str] = []
    try:
        rows = _exec_catalog_query(
            "SELECT tablename, policyname FROM pg_policies WHERE schemaname = 'public'"
        )
    except Exception as exc:
        logger.error("  FAIL policy catalog query: %s", exc)
        return False, ["rls_policy_check_unavailable"]

    policies = {(row["tablename"], row["policyname"]) for row in rows}
    for table_name, policy_name in REQUIRED_POLICIES.items():
        if (table_name, policy_name) in policies:
            logger.info("  OK %s.%s", table_name, policy_name)
        else:
            logger.error("  FAIL %s.%s missing", table_name, policy_name)
            missing.append(f"{table_name}.{policy_name}")

    return len(missing) == 0, missing


def check_indexes() -> Tuple[bool, List[str]]:
    logger.info("Checking indexes...")
    missing: List[str] = []
    try:
        rows = _exec_catalog_query(
            "SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public'"
        )
    except Exception as exc:
        logger.error("  FAIL index catalog query: %s", exc)
        return False, ["index_check_unavailable"]

    indexes = {(row["tablename"], row["indexname"]) for row in rows}
    for table_name, index_name in REQUIRED_INDEXES:
        if (table_name, index_name) in indexes:
            logger.info("  OK %s.%s", table_name, index_name)
        else:
            logger.error("  FAIL %s.%s missing", table_name, index_name)
            missing.append(f"{table_name}.{index_name}")

    return len(missing) == 0, missing


def check_rpc_functions() -> Tuple[bool, List[str]]:
    logger.info("Checking RPC functions...")
    missing: List[str] = []
    try:
        rows = _exec_catalog_query(
            "SELECT proname FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid "
            "WHERE n.nspname='public'"
        )
        names = {row.get("proname") for row in rows}
    except Exception as exc:
        logger.error("  FAIL RPC catalog query: %s", exc)
        return False, ["rpc_function_check_unavailable"]

    for func_name in REQUIRED_FUNCTIONS:
        if func_name in names:
            logger.info("  OK %s", func_name)
        else:
            logger.error("  FAIL %s missing", func_name)
            missing.append(func_name)

    return len(missing) == 0, missing


def check_environment_variables() -> Tuple[bool, List[str]]:
    logger.info("Checking environment variables...")
    missing: List[str] = []

    for env_var in REQUIRED_ENV_VARS:
        value = getattr(settings, env_var.lower(), None)
        if value:
            if "key" in env_var.lower() or "secret" in env_var.lower():
                masked = value[:8] + "..." if len(value) > 8 else "***"
                logger.info("  OK %s=%s", env_var, masked)
            else:
                logger.info("  OK %s=%s", env_var, value)
        else:
            logger.error("  FAIL %s missing", env_var)
            missing.append(env_var)

    return len(missing) == 0, missing


def check_service_role_key() -> bool:
    logger.info("Checking service role key format...")
    key = settings.supabase_service_role_key
    if len(key) < 100:
        logger.error("  FAIL key too short (likely anon key)")
        return False
    if not key.startswith("eyJ"):
        logger.error("  FAIL key is not JWT-like")
        return False
    logger.info("  OK service role key looks valid")
    return True


def main() -> int:
    logger.info("=" * 60)
    logger.info("Supabase setup validation started")
    logger.info("=" * 60)

    all_checks_passed = True

    env_ok, missing_env = check_environment_variables()
    all_checks_passed &= env_ok

    service_role_ok = check_service_role_key()
    all_checks_passed &= service_role_ok

    tables_ok, missing_tables = check_tables()
    all_checks_passed &= tables_ok

    policies_ok, missing_policies = check_rls_policies()
    all_checks_passed &= policies_ok

    indexes_ok, missing_indexes = check_indexes()
    all_checks_passed &= indexes_ok

    functions_ok, missing_functions = check_rpc_functions()
    all_checks_passed &= functions_ok

    logger.info("")
    logger.info("=" * 60)
    logger.info("Validation summary")
    logger.info("=" * 60)

    if all_checks_passed:
        logger.info("All checks passed")
        return 0

    logger.error("Validation failed")
    if missing_env:
        logger.error("  Missing env: %s", ", ".join(missing_env))
    if missing_tables:
        logger.error("  Missing tables: %s", ", ".join(missing_tables))
    if missing_policies:
        logger.error("  Missing policies: %s", ", ".join(missing_policies))
    if missing_indexes:
        logger.error("  Missing indexes: %s", ", ".join(missing_indexes))
    if missing_functions:
        logger.error("  Missing functions: %s", ", ".join(missing_functions))
    return 1


if __name__ == "__main__":
    sys.exit(main())
