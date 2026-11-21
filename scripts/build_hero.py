#!/usr/bin/env python3
"""첫 화면 예시 애니메이션의 숫자 -> app/web/hero.json.

화면에 나오는 금액은 계산 모듈(calc_net_pay)과 월세 통계(get_rent_stats)의 출력만 쓴다.
월세 스냅샷을 다시 만들면 이 스크립트도 다시 돌린다.
예) python3 scripts/build_hero.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.calc.netpay import calc_net_pay  # noqa: E402
from app.data.regions import get_region  # noqa: E402
from app.data.rent import get_rent_stats, snapshot_info  # noqa: E402

# 예시 두 건: 연봉이 높은 수도권 공고와 연봉이 낮은 지역 공고. 감면 없음, 비과세 식대 월 20만 원.
EXAMPLES = [("서울", "11680", 38_000_000), ("부산", "26230", 34_000_000)]
NON_TAXABLE_MONTHLY = 200_000


def build() -> dict:
    jobs = []
    for label, code, salary in EXAMPLES:
        pay = calc_net_pay(salary, NON_TAXABLE_MONTHLY, False)
        rent = get_rent_stats(code)
        region = get_region(code)
        if rent is None or region is None:
            raise SystemExit(f"{code}: 월세 통계나 지역 정보가 없습니다")
        rent_annual = rent.monthly_median * 12
        jobs.append({
            "label": label, "sggCode": code, "region": region.name,
            "salary": salary,
            "taxAndInsurance": salary - pay.net_annual,
            "rentAnnual": rent_annual, "rentMonthly": rent.monthly_median,
            "remaining": pay.net_annual - rent_annual,
        })
    info = snapshot_info()
    return {"jobs": jobs, "rentVersion": info["version"], "rentPeriod": get_rent_stats(EXAMPLES[0][1]).period,
            "assumption": "1년차, 감면 없음, 비과세 식대 월 20만 원, 원룸 월세 중위값"}


if __name__ == "__main__":
    out = ROOT / "app" / "web" / "hero.json"
    data = build()
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for j in data["jobs"]:
        print(j["label"], j["salary"], "->", j["remaining"])
    print("저장:", out)
