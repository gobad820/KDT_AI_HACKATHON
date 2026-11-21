#!/usr/bin/env python3
"""쇼릴 영상용 숫자 -> media/showreel/data.json. 금액은 계산 모듈·월세 통계 출력만 쓴다.
예) python3 media/showreel/build_data.py
"""
import csv
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHORT = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "대전광역시": "대전",
         "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원", "충청북도": "충북",
         "충청남도": "충남", "전북특별자치도": "전북", "전남광주통합특별시": "전남광주", "경상북도": "경북",
         "경상남도": "경남", "제주특별자치도": "제주"}

hero = json.loads((ROOT / "app/web/hero.json").read_text(encoding="utf-8"))
stats = json.loads((ROOT / "data/rent_stats.json").read_text(encoding="utf-8"))
names = {}
with open(ROOT / "data/regions.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        names[r["sggCode"]] = (SHORT.get(r["sidoName"], r["sidoName"]) + " " + (r["sggName"] or "")).strip()
rows = []
for code, v in stats["stats"].items():
    s = v.get("sgg")
    if s and s.get("sampleCount", 0) >= 30 and code in names:
        rows.append({"name": names[code], "median": s["monthlyMedian"]})
rows.sort(key=lambda r: -r["median"])
con = sqlite3.connect(ROOT / "data/rent.sqlite")
deals = con.execute("SELECT COUNT(*) FROM rent_deals WHERE deal_ym BETWEEN '202511' AND '202610'").fetchone()[0]
out = {"jobs": hero["jobs"], "rentPeriod": hero["rentPeriod"], "rentVersion": stats["version"],
       "deals": deals, "sggCount": len(stats["stats"]), "rows": rows}
(Path(__file__).parent / "data.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("deals", deals, "sgg", out["sggCount"], "rows", len(rows), "top", rows[:2], "bottom", rows[-1:])
