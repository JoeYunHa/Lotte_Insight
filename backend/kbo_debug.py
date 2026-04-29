"""
Register.aspx POST 응답의 테이블 HTML 구조 진단.

사용:
    cd lotte-insight/backend
    python kbo_debug.py
"""

import requests
from bs4 import BeautifulSoup
from datetime import date

URL = "https://www.koreabaseball.com/Player/Register.aspx"
UA  = "LotteInsightBot/1.0 (contact: jojojo7391@gmail.com)"

session = requests.Session()
session.headers.update({"User-Agent": UA, "Referer": URL})

# 초기 GET
resp = session.get(URL, timeout=30)
soup = BeautifulSoup(resp.text, "lxml")

def hidden(name):
    el = soup.find("input", {"name": name})
    return el.get("value", "") if el else ""

TEAM_FIELD  = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$hfSearchTeam"
DATE_FIELD  = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$hfSearchDate"
EVENT_TGT   = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$btnCalendarSelect"

search_date = hidden(DATE_FIELD) or date.today().strftime("%Y%m%d")

post_data = {
    "__VIEWSTATE":          hidden("__VIEWSTATE"),
    "__VIEWSTATEGENERATOR": hidden("__VIEWSTATEGENERATOR"),
    "__EVENTVALIDATION":    hidden("__EVENTVALIDATION"),
    "__EVENTTARGET":        EVENT_TGT,
    "__EVENTARGUMENT":      "",
    TEAM_FIELD:             "LT",
    DATE_FIELD:             search_date,
}

resp2 = session.post(URL, data=post_data, timeout=30)
resp2.encoding = resp2.apparent_encoding
soup2 = BeautifulSoup(resp2.text, "lxml")

tables = soup2.find_all("table")
print(f"테이블 수: {len(tables)}\n")

for t_idx, table in enumerate(tables):
    rows = table.find_all("tr")
    print(f"=== 테이블 {t_idx} ({len(rows)}행) ===")
    for r_idx, tr in enumerate(rows[:8]):  # 최대 8행만 출력
        cells = tr.find_all(["td", "th"])
        cell_info = []
        for c in cells:
            colspan = c.get("colspan", "")
            cls     = c.get("class", "")
            text    = c.get_text(strip=True)[:30]
            cell_info.append(f"[colspan={colspan} class={cls}] {text!r}")
        print(f"  행{r_idx}: {cell_info}")
    if len(rows) > 8:
        print(f"  ... ({len(rows) - 8}행 생략)")
    print()
