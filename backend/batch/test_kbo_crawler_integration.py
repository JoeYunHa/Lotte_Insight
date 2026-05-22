"""
Integration smoke test for the KBO crawler.

실행 방법:
  python -m pytest backend/batch/test_kbo_crawler_integration.py -v
  python backend/batch/test_kbo_crawler_integration.py [--save]

playwright, pydantic_settings 가 설치되지 않은 환경에서는 파일 전체가 skip된다.
"""

import argparse
import logging
import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("playwright", reason="playwright not installed — skipping KBO crawler tests")
pytest.importorskip("pydantic_settings", reason="pydantic_settings not installed — skipping KBO crawler tests")

from batch.kbo_crawler import (  # noqa: E402
    _STAT_MAP,
    _URLS,
    _can_fetch,
    _parse_table,
    _select_team_and_get_html,
    run,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"


def test_robots_txt():
    print("\n[1] robots.txt access")
    all_ok = True
    for key, url in _URLS.items():
        allowed = _can_fetch(url)
        print(f"  {(PASS if allowed else FAIL)} {key}: {'allowed' if allowed else 'blocked'}")
        if not allowed:
            all_ok = False
    return all_ok


def test_fetch_and_parse():
    print("\n[2] fetch and parse")
    all_ok = True

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        for page_key, url in _URLS.items():
            print(f"\n  [{page_key}]")
            html = _select_team_and_get_html(page, url)
            if html is None:
                print(f"  {FAIL} failed to fetch HTML")
                all_ok = False
                continue

            rows = _parse_table(html, _STAT_MAP[page_key])
            if not rows:
                print(f"  {FAIL} no parsed rows")
                all_ok = False
            else:
                print(f"  {PASS} parsed {len(rows)} rows")

        browser.close()

    return all_ok


def test_run_dry():
    print("\n[3] dry run")

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.execute.return_value.data = []
    mock_supabase.table.return_value.upsert.return_value.execute.return_value = None

    # kbo_crawler.run() 은 load_supabase() 반환값을 지역 변수로 사용하므로
    # 모듈 레벨 'supabase' 심볼 패치가 아닌 load_supabase 자체를 교체해야 DB 격리가 된다.
    with patch("batch.kbo_crawler.load_supabase", return_value=mock_supabase):
        result = run(target_date=date.today())

    ok = {"saved", "unmatched", "date"}.issubset(result.keys())
    print(f"  {(PASS if ok else FAIL)} result={result}")
    return ok


def test_run_save():
    print("\n[4] save run")
    result = run(target_date=date.today())
    ok = result["saved"] >= 0
    print(f"  {(PASS if ok else FAIL)} result={result}")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true", help="Persist results to DB")
    args = parser.parse_args()

    results = [test_robots_txt(), test_fetch_and_parse()]
    results.append(test_run_save() if args.save else test_run_dry())

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    if passed == total:
        print(f"{PASS} all {total} tests passed")
    else:
        print(f"{FAIL} {total - passed} / {total} tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
