"""
Debug helper for KBO Register.aspx structure.
"""

import argparse
import re
from datetime import date

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from batch.kbo_crawler import (
    _REG_DATE_FIELD,
    _REG_EVENT_TARGET,
    _REG_TEAM_FIELD,
    _REGISTER_URL,
    _extract_update_panel,
)
from core.config import settings


def _debug_register_post():
    session = requests.Session()
    session.headers.update({"User-Agent": settings.crawl_user_agent, "Referer": _REGISTER_URL})

    response = session.get(_REGISTER_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    def hidden(name: str) -> str:
        element = soup.find("input", {"name": name})
        return element.get("value", "") if element else ""

    search_date = hidden(_REG_DATE_FIELD) or date.today().strftime("%Y%m%d")
    post_data = {
        "__VIEWSTATE": hidden("__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": hidden("__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": hidden("__EVENTVALIDATION"),
        "__EVENTTARGET": _REG_EVENT_TARGET,
        "__EVENTARGUMENT": "",
        _REG_TEAM_FIELD: settings.team_code,
        _REG_DATE_FIELD: search_date,
    }

    response2 = session.post(_REGISTER_URL, data=post_data, timeout=30)
    response2.raise_for_status()
    response2.encoding = response2.apparent_encoding
    html = _extract_update_panel(response2.text)
    soup2 = BeautifulSoup(html, "lxml")

    tables = soup2.find_all("table")
    print(f"tables={len(tables)}")
    for table_index, table in enumerate(tables):
        rows = table.find_all("tr")
        print(f"=== table {table_index} ({len(rows)} rows) ===")
        for row_index, tr in enumerate(rows[:8]):
            cells = tr.find_all(["td", "th"])
            cell_info = []
            for cell in cells:
                colspan = cell.get("colspan", "")
                cls = cell.get("class", "")
                text = cell.get_text(strip=True)[:30]
                cell_info.append(f"[colspan={colspan} class={cls}] {text!r}")
            print(f"  row {row_index}: {cell_info}")
        if len(rows) > 8:
            print(f"  ... ({len(rows) - 8} more rows)")


def _debug_register_page():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(_REGISTER_URL, wait_until="networkidle", timeout=30000)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "lxml")
    for select in soup.find_all("select"):
        print(f"\n[SELECT] name={select.get('name')} id={select.get('id')}")
        for option in select.find_all("option"):
            print(f"  value={option.get('value')!r:10s} text={option.get_text(strip=True)}")

    print("\n[TEAM LINKS]")
    for anchor in soup.find_all("a", href=re.compile(r"fnSearch|teamCode|team", re.I)):
        print(f"  href={anchor.get('href')} text={anchor.get_text(strip=True)}")

    for form in soup.find_all("form"):
        print(f"\n[FORM] action={form.get('action')} method={form.get('method')}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("register", "page"), default="register")
    args = parser.parse_args()

    if args.mode == "register":
        _debug_register_post()
    else:
        _debug_register_page()


if __name__ == "__main__":
    main()
