"""
Cache Key Builder

Centralized cache key generation for consistent naming across the application.
All cache keys should be generated through this module to ensure:
1. Consistent naming patterns
2. No key collisions
3. Easy cache invalidation
4. Better monitoring/debugging
"""

from __future__ import annotations

from datetime import date


class CacheKeyBuilder:
    """
    Centralized cache key builder for the application.

    Naming convention:
    - Pattern: `{namespace}:{entity}:{identifiers}`
    - Example: `review:fanvoice:home:today:2026-05-28:final`

    This aligns with existing project patterns:
    - `report:team:{date}`
    - `report:player:{id}:{date}`
    """

    # Namespaces
    NAMESPACE_REVIEW = "review"
    NAMESPACE_REPORT = "report"

    # Entities
    ENTITY_FANVOICE = "fanvoice"
    ENTITY_TEAM = "team"
    ENTITY_PLAYER = "player"

    @staticmethod
    def _date_str(d: "date | str") -> str:
        return d.isoformat() if isinstance(d, date) else str(d)

    @staticmethod
    def fan_voice_review(
        *,
        context_type: str,
        context_id: str,
        game_date: date,
        review_type: str,
    ) -> str:
        """
        Generate cache key for fan voice daily review.

        Format: review:fanvoice:{context_type}:{context_id}:{game_date}:{review_type}
        Example: review:fanvoice:home:today:2026-05-28:final

        Args:
            context_type: Context type (e.g., 'home', 'player')
            context_id: Context ID (e.g., 'today', player_id)
            game_date: Game date
            review_type: Review type ('final', 'interim')

        Returns:
            Cache key string
        """
        return f"{CacheKeyBuilder.NAMESPACE_REVIEW}:{CacheKeyBuilder.ENTITY_FANVOICE}:{context_type}:{context_id}:{CacheKeyBuilder._date_str(game_date)}:{review_type}"

    @staticmethod
    def team_report(*, report_date: date) -> str:
        """
        Generate cache key for team daily report.

        Format: report:team:{date}
        Example: report:team:2026-05-28

        Args:
            report_date: Report date

        Returns:
            Cache key string
        """
        return f"{CacheKeyBuilder.NAMESPACE_REPORT}:{CacheKeyBuilder.ENTITY_TEAM}:{CacheKeyBuilder._date_str(report_date)}"

    @staticmethod
    def player_report(*, player_id: int, report_date: date) -> str:
        """
        Generate cache key for player daily report.

        Format: report:player:{player_id}:{date}
        Example: report:player:123:2026-05-28

        Args:
            player_id: Player ID
            report_date: Report date

        Returns:
            Cache key string
        """
        return f"{CacheKeyBuilder.NAMESPACE_REPORT}:{CacheKeyBuilder.ENTITY_PLAYER}:{player_id}:{CacheKeyBuilder._date_str(report_date)}"

    @staticmethod
    def home_report(*, report_date: date) -> str:
        """
        Generate cache key for home aggregate report.

        Format: report:home:{date}
        Example: report:home:2026-05-28
        """
        return f"{CacheKeyBuilder.NAMESPACE_REPORT}:home:{CacheKeyBuilder._date_str(report_date)}"

    @staticmethod
    def team_report_list(*, limit: int) -> str:
        """Format: report:team:list:{limit}"""
        return f"{CacheKeyBuilder.NAMESPACE_REPORT}:{CacheKeyBuilder.ENTITY_TEAM}:list:{limit}"

    @staticmethod
    def player_report_list(*, player_id: int, limit: int) -> str:
        """Format: report:player:{player_id}:list:{limit}"""
        return f"{CacheKeyBuilder.NAMESPACE_REPORT}:{CacheKeyBuilder.ENTITY_PLAYER}:{player_id}:list:{limit}"

    @staticmethod
    def topic_map(*, map_date: date) -> str:
        """Format: topic:map:{date}"""
        return f"topic:map:{CacheKeyBuilder._date_str(map_date)}"

    @staticmethod
    def player_list(*, status: str | None) -> str:
        """Format: player:list:{status|all}"""
        return f"player:list:{status or 'all'}"

    @staticmethod
    def player_detail(*, player_id: int, stats_date: date | None) -> str:
        """Format: player:{player_id}:stats:{date|latest}"""
        date_str = CacheKeyBuilder._date_str(stats_date) if stats_date else "latest"
        return f"player:{player_id}:stats:{date_str}"

    @staticmethod
    def rate_limit_context_writes(context_type: str, context_id: str) -> str:
        """Format: fanvoice:writes:{context_type}:{context_id}"""
        return f"fanvoice:writes:{context_type}:{context_id}"

    @staticmethod
    def rate_limit_session_last_write(session_id: int) -> str:
        """Format: fanvoice:session:last_write:{session_id}"""
        return f"fanvoice:session:last_write:{session_id}"

    @staticmethod
    def rate_limit_session_recent_msg(session_id: int) -> str:
        """Format: fanvoice:session:recent_msg:{session_id}"""
        return f"fanvoice:session:recent_msg:{session_id}"


# Convenience aliases
def fanvoice_review_key(**kwargs) -> str:
    return CacheKeyBuilder.fan_voice_review(**kwargs)


def team_report_key(**kwargs) -> str:
    return CacheKeyBuilder.team_report(**kwargs)


def player_report_key(**kwargs) -> str:
    return CacheKeyBuilder.player_report(**kwargs)


def home_report_key(**kwargs) -> str:
    return CacheKeyBuilder.home_report(**kwargs)


def team_report_list_key(**kwargs) -> str:
    return CacheKeyBuilder.team_report_list(**kwargs)


def player_report_list_key(**kwargs) -> str:
    return CacheKeyBuilder.player_report_list(**kwargs)
