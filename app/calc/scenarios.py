"""시나리오별 누적 남는 돈과 손익분기 연봉. 정의는 docs/calc-rules.md 6, 7장.

가정: 같은 회사, 같은 연봉, 같은 월세, 2026년 요율이 유지된다. 1월 입사로 보고 연 단위로 처리한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional

from app.schemas import SCENARIO_IDS, BreakEven, Comparison, Pay, PayPair, Scenario, YearRow

from . import constants as C
from .netpay import NetPay, calc_net_pay


@dataclass(frozen=True)
class SimJob:
    id: str
    annual_salary: int
    non_taxable_monthly: int
    housing_monthly: int
    type_base: int        # 정부안 유형 (우대지역 아님)
    type_pref: int        # 정부안 유형 (우대지역으로 지정될 때)
    eligible: bool        # 감면 대상 가능성이 unlikely 면 False


@dataclass
class SimResult:
    pay: Dict[str, PayPair]
    scenarios: Dict[str, List[Scenario]]
    comparison: List[Comparison]


@lru_cache(maxsize=4096)
def _net(annual_salary: int, non_taxable_monthly: int, relief: bool) -> NetPay:
    return calc_net_pay(annual_salary, non_taxable_monthly, relief)


def relief_years(scenario_id: str, job: SimJob, hire_year: int) -> int:
    """시나리오별 감면 적용 연수."""
    if not job.eligible or scenario_id == "none":
        return 0
    if scenario_id == "current_law":
        return C.CURRENT_LAW_YEARS if hire_year <= C.CURRENT_LAW_LAST_HIRE_YEAR else 0
    if scenario_id == "proposal_base":
        return C.RELIEF_YEARS_BY_TYPE[job.type_base]
    if scenario_id == "proposal_pref":
        return C.RELIEF_YEARS_BY_TYPE[job.type_pref]
    raise ValueError(f"알 수 없는 시나리오: {scenario_id}")


def cumulative_remaining(annual_salary: int, non_taxable_monthly: int, housing_monthly: int,
                         years_with_relief: int, horizon_years: int) -> int:
    with_relief = _net(annual_salary, non_taxable_monthly, True).net_annual
    without = _net(annual_salary, non_taxable_monthly, False).net_annual
    n = min(years_with_relief, horizon_years)
    return with_relief * n + without * (horizon_years - n) - housing_monthly * 12 * horizon_years


def _scenario(job: SimJob, scenario_id: str, hire_year: int, horizon_years: int) -> Scenario:
    years = relief_years(scenario_id, job, hire_year)
    with_relief = _net(job.annual_salary, job.non_taxable_monthly, True).net_annual
    without = _net(job.annual_salary, job.non_taxable_monthly, False).net_annual
    housing = job.housing_monthly * 12
    yearly, cumulative = [], 0
    for year in range(1, horizon_years + 1):
        applied = year <= years
        net = with_relief if applied else without
        cumulative += net - housing
        yearly.append(YearRow(year=year, relief_applied=applied, net_annual=net, housing_annual=housing,
                              remaining=net - housing, cumulative=cumulative))
    return Scenario(id=scenario_id, relief_years=years, first_year_remaining=yearly[0].remaining,
                    cumulative_remaining=cumulative,
                    relief_total=(with_relief - without) * min(years, horizon_years), yearly=yearly)


def break_even_salary(target_cumulative: int, job: SimJob, years_with_relief: int,
                      horizon_years: int) -> Optional[int]:
    """누적 남는 돈이 target 이상이 되는 가장 낮은 연봉 (만 원 단위). 범위 안에 없으면 None."""
    def cum(k: int) -> int:
        return cumulative_remaining(k * 10_000, job.non_taxable_monthly, job.housing_monthly,
                                    years_with_relief, horizon_years)

    lo, hi = C.BREAK_EVEN_MIN // 10_000, C.BREAK_EVEN_MAX // 10_000
    if cum(hi) < target_cumulative:
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if cum(mid) >= target_cumulative:
            hi = mid
        else:
            lo = mid + 1
    return lo * 10_000


def _pay(n: NetPay) -> Pay:
    return Pay(insurance=n.insurance, final_tax=n.final_tax, local_tax=n.local_tax,
               net_annual=n.net_annual, net_monthly_avg=n.net_monthly_avg)


def simulate(jobs: List[SimJob], hire_year: int, horizon_years: int) -> SimResult:
    """공고 두 건의 시나리오 4개와 비교 결과."""
    if len(jobs) != 2:
        raise ValueError("공고는 두 건이어야 한다")
    if horizon_years < 1:
        raise ValueError("누적 기간은 1년 이상이어야 한다")
    pay = {j.id: PayPair(none=_pay(_net(j.annual_salary, j.non_taxable_monthly, False)),
                         with_relief=_pay(_net(j.annual_salary, j.non_taxable_monthly, True))) for j in jobs}
    scenarios = {j.id: [_scenario(j, sid, hire_year, horizon_years) for sid in SCENARIO_IDS] for j in jobs}

    first, second = jobs
    comparison = []
    for i, sid in enumerate(SCENARIO_IDS):
        s1, s2 = scenarios[first.id][i], scenarios[second.id][i]
        if s1.cumulative_remaining >= s2.cumulative_remaining:   # 같으면 첫 번째 공고
            better, worse, target = first, second, s1.cumulative_remaining
            worse_years = s2.relief_years
        else:
            better, worse, target = second, first, s2.cumulative_remaining
            worse_years = s1.relief_years
        difference = abs(s1.cumulative_remaining - s2.cumulative_remaining)
        break_even = None
        if difference > 0:
            salary = break_even_salary(target, worse, worse_years, horizon_years)
            if salary is not None:
                break_even = BreakEven(job_id=worse.id, annual_salary=salary)
        comparison.append(Comparison(scenario_id=sid, better_job_id=better.id, difference=difference,
                                     break_even=break_even))
    return SimResult(pay=pay, scenarios=scenarios, comparison=comparison)
