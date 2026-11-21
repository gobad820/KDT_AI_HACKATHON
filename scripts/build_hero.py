#!/usr/bin/env python3
"""첫 화면 예시 애니메이션의 숫자 -> app/web/hero.json.

화면에 나오는 금액은 계산 모듈(calc_net_pay, simulate)과 월세 통계(get_rent_stats)의 출력만 쓴다.
- jobs[].salary·taxAndInsurance·rentAnnual·remaining: 1년차. 첫 화면 영상의 영수증에 구운 숫자다
- jobs[].cumulativeRemaining, comparison.difference: HORIZON_YEARS년 누적. simulate의 '감면 없음'(none) 시나리오 출력
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
from app.calc.scenarios import SimJob, simulate  # noqa: E402
from app.data.regions import get_region  # noqa: E402
from app.data.rent import get_rent_stats, snapshot_info  # noqa: E402

# 예시 두 건: 연봉이 높은 수도권 공고와 연봉이 낮은 지역 공고. 감면 없음, 비과세 식대 월 20만 원.
EXAMPLES = [("서울", "11680", 38_000_000), ("부산", "26230", 34_000_000)]
NON_TAXABLE_MONTHLY = 200_000
HORIZON_YEARS = 10          # 결과 화면 기본 누적 기간과 같다(app/schemas.py CompareOptions)
HIRE_YEAR = 2027            # 감면 없음 시나리오만 쓰므로 금액에 영향 없음


def build() -> dict:
    jobs, sim_jobs = [], []
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
        sim_jobs.append(SimJob(id=label, annual_salary=salary, non_taxable_monthly=NON_TAXABLE_MONTHLY,
                               housing_monthly=rent.monthly_median, type_base=region.type_base,
                               type_pref=region.type_pref, eligible=False))

    # 같은 연봉과 월세가 HORIZON_YEARS년 동안 이어진다고 보고 누적한다(감면 없음)
    sim = simulate(sim_jobs, HIRE_YEAR, HORIZON_YEARS)
    for job in jobs:
        none = next(s for s in sim.scenarios[job["label"]] if s.id == "none")
        if none.first_year_remaining != job["remaining"]:
            raise SystemExit(f"{job['label']}: 1년차 금액이 계산 모듈과 다릅니다")
        job["cumulativeRemaining"] = none.cumulative_remaining
    comp = next(c for c in sim.comparison if c.scenario_id == "none")

    info = snapshot_info()
    return {"jobs": jobs, "horizonYears": HORIZON_YEARS,
            "comparison": {"scenarioId": comp.scenario_id, "betterJob": comp.better_job_id,
                           "difference": comp.difference},
            "rentVersion": info["version"], "rentPeriod": get_rent_stats(EXAMPLES[0][1]).period,
            "assumption": f"1년차와 {HORIZON_YEARS}년 누적(같은 연봉·월세 유지), 감면 없음, 비과세 식대 월 20만 원, 원룸 월세 중위값"}


if __name__ == "__main__":
    out = ROOT / "app" / "web" / "hero.json"
    data = build()
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for j in data["jobs"]:
        print(j["label"], j["salary"], "-> 1년", j["remaining"], f"/ {data['horizonYears']}년", j["cumulativeRemaining"])
    print(f"{data['horizonYears']}년 차이:", data["comparison"]["betterJob"], data["comparison"]["difference"])
    print("저장:", out)
