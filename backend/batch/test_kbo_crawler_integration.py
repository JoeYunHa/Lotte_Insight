"""
KBO 크롤러 통합 테스트.

실제 KBO 사이트에 Playwright 헤드리스 브라우저로 접속하고 파싱 결과를 검증한다.
DB 쓰기는 --save 플래그 없이는 실행되지 않는다 (dry-run 기본).

실행:
    python batch/test_kbo_crawler_integration.py           # dry-run
    python batch/test_kbo_crawler_integration.py --save    # DB 실제 저장
"""

import argparse
import logging
import sys
import os
from datetime import date
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

from batch.kbo_crawler import (
    _can_fetch,
    _fetch_lotte_stats,
    _parse_table,
    _URLS,
    _STAT_MAP,
    run,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"


# ── 개별 테스트 ────────────────────────────────────────────────────────────────

def test_robots_txt():
    """KBO 수집 대상 URL이 robots.txt에 의해 허용되는지 확인."""
    print("\n[1] robots.txt 허용 여부")
    all_ok = True
    for key, url in _URLS.items():
        allowed = _can_fetch(url)
        status = PASS if allowed else FAIL
        print(f"  {status} {key}: {'허용' if allowed else '금지'}")
        if not allowed:
            all_ok = False
    return all_ok


def test_fetch_and_parse():
    """
    Playwright로 각 페이지를 실제 수집하고, 롯데 선수 행이 파싱되는지 확인.
    브라우저 1개를 3개 URL에 재사용한다.
    """
    print("\n[2] HTTP 수집 및 파싱 (Playwright)")
    all_ok = True

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        for page_key, url in _URLS.items():
            print(f"\n  [{page_key}]")
            html = _fetch_lotte_stats(page, url)

            if html is None:
                print(f"  {FAIL} HTML 수신 실패")
                all_ok = False
                continue

            rows = _parse_table(html, _STAT_MAP[page_key])

            if not rows:
                print(f"  {FAIL} 파싱된 롯데 선수 없음")
                # 파싱 실패 시 tbody 여부와 응답 길이만 출력
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "lxml")
                tbodies = soup.find_all("tbody")
                print(f"    응답 길이: {len(html)}  <tbody> 수: {len(tbodies)}")
                all_ok = False
            else:
                print(f"  {PASS} 롯데 선수 {len(rows)}명 파싱")
                for r in rows:
                    stats_str = "  ".join(
                        f"{k}={v}" for k, v in r.items()
                        if k not in ("name", "kbo_player_id") and v is not None
                    )
                    print(f"    · {r['name']} (id={r['kbo_player_id']})  {stats_str}")

        browser.close()

    return all_ok


def test_run_dry():
    """
    run()을 실행하되 DB upsert를 mock으로 대체.
    반환값(saved, unmatched, date)이 올바른 형태인지 확인.
    """
    print("\n[3] run() dry-run (DB mock)")

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.execute.return_value.data = []
    mock_supabase.table.return_value.upsert.return_value.execute.return_value = None

    with patch("batch.kbo_crawler.supabase", mock_supabase):
        result = run(target_date=date.today())

    required_keys = {"saved", "unmatched", "date"}
    ok = required_keys.issubset(result.keys())
    status = PASS if ok else FAIL
    print(f"  {status} 반환값: {result}")
    return ok


def test_run_save():
    """실제 DB에 저장. --save 플래그 시에만 실행."""
    print("\n[4] run() 실제 저장")
    result = run(target_date=date.today())
    ok = result["saved"] >= 0
    status = PASS if ok else FAIL
    print(f"  {status} 저장 결과: {result}")
    return ok


# ── 실행 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true", help="실제 DB에 저장")
    args = parser.parse_args()

    results: list[bool] = []

    results.append(test_robots_txt())
    results.append(test_fetch_and_parse())

    if args.save:
        results.append(test_run_save())
    else:
        results.append(test_run_dry())

    print("\n" + "─" * 50)
    passed = sum(results)
    total = len(results)
    if passed == total:
        print(f"{PASS} 전체 {total}개 테스트 통과")
    else:
        print(f"{FAIL} {total}개 중 {total - passed}개 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
