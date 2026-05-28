from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime

from services import fan_voice_review_service

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate fan voice daily opinion review")
    parser.add_argument("--date", dest="target_date", help="Target date in YYYY-MM-DD format")
    parser.add_argument(
        "--review-type",
        dest="review_type",
        default="final",
        choices=["interim", "final"],
        help="Review type to generate",
    )
    parser.add_argument(
        "--context-type",
        dest="context_type",
        default="home",
        help="Context type (default: home)",
    )
    parser.add_argument(
        "--context-id",
        dest="context_id",
        default="today",
        help="Context id (default: today)",
    )
    parser.add_argument(
        "--min-messages",
        dest="min_messages",
        type=int,
        default=20,
        help="Minimum message count required for full review generation",
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> dict:
    args = _parse_args(argv)
    requested_date: date | None = None
    if args.target_date:
        requested_date = datetime.strptime(args.target_date, "%Y-%m-%d").date()
        scope = "date"
    else:
        scope = "today_or_latest"

    logger.info(
        "fan_voice_review_generator started scope=%s date=%s review_type=%s context=%s:%s",
        scope,
        requested_date.isoformat() if requested_date else "-",
        args.review_type,
        args.context_type,
        args.context_id,
    )

    result = fan_voice_review_service.generate_daily_review(
        scope=scope,
        requested_date=requested_date,
        context_type=args.context_type,
        context_id=args.context_id,
        review_type=args.review_type,
        min_messages=max(1, args.min_messages),
    )
    logger.info("fan_voice_review_generator completed status=%s", result.get("status", "completed"))
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    output = run()
    print(output)
    sys.exit(0)
