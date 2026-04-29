# entry_debug2.py — 팀 선택 UI 구조 파악
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www.koreabaseball.com/Player/Register.aspx",
            wait_until="networkidle", timeout=30000)
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, "lxml")

# 1. select 드롭다운 전체 출력

soup = BeautifulSoup(html, "lxml")

# 1. select 드롭다운 전체 출력
for sel in soup.find_all("select"):
    print(f"\n[SELECT] name={sel.get('name')} id={sel.get('id')}")
    for opt in sel.find_all("option"):
        print(f"  value={opt.get('value')!r:10s}  text={opt.get_text(strip=True)}")

# 2. 팀 관련 링크/버튼
print("\n[TEAM LINKS]")
import re
for a in soup.find_all("a", href=re.compile(r"fnSearch|teamCode|team", re.I)):
    print(f"  href={a.get('href')}  text={a.get_text(strip=True)}")

# 3. form action 확인
for form in soup.find_all("form"):
    print(f"\n[FORM] action={form.get('action')} method={form.get('method')}")