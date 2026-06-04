"""Print article history coverage from Supabase.

Usage:
    python backend/scripts/audit_article_history.py --before 2026-01-01
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.bootstrap import load_supabase  # noqa: E402


def fetch_history_summary(before: str | None = None) -> dict:
    supabase = load_supabase()
    query = supabase.table("articles").select("id, published_at", count="exact")
    if before:
        query = query.lt("published_at", before)
    response = query.order("published_at", desc=False).limit(1).execute()

    count = getattr(response, "count", None)
    first = (response.data or [{}])[0].get("published_at") if response.data else None

    latest_query = supabase.table("articles").select("published_at")
    if before:
        latest_query = latest_query.lt("published_at", before)
    latest_response = latest_query.order("published_at", desc=True).limit(1).execute()
    latest = (latest_response.data or [{}])[0].get("published_at") if latest_response.data else None

    return {"count": count, "min_published_at": first, "max_published_at": latest}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit article coverage in Supabase.")
    parser.add_argument("--before", default=None, help="Optional upper bound, e.g. 2026-01-01")
    args = parser.parse_args(argv)

    summary = fetch_history_summary(before=args.before)
    print(f"count: {summary['count']}")
    print(f"min_published_at: {summary['min_published_at']}")
    print(f"max_published_at: {summary['max_published_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
