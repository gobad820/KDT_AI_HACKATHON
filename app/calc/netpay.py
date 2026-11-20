"""연봉 -> 연간 세후 금액. 단계는 docs/calc-rules.md 3장과 같다.

가정: 1인 가구, 근로소득만 있음, 12개월 근무, 그 밖의 공제 없음.
공식 계산기와 대조하기 전이다 (docs/calc-rules.md 8장).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction as F

from . import constants as C


@dataclass(frozen=True)
class NetPay:
    annual_salary: int
    non_taxable_annual: int
    total_pay: int            # 총급여
    pension: int              # 4대보험 연액
    health: int
    ltc: int
    employ: int
    insurance: int
    wage_income: int          # 근로소득금액
    tax_base: int             # 과세표준
    calc_tax: int             # 산출세액
    relief_tax: int           # 감면세액
    wage_credit: int          # 근로소득세액공제 (감면 조정 후)
    standard_credit: int      # 표준세액공제
    final_tax: int            # 결정세액
    local_tax: int            # 지방소득세
    net_annual: int           # 세후 연봉
    net_monthly_avg: int
    option: str               # "insurance_deduction"(가 경로) | "standard_credit"(나 경로)


def floor10(x) -> int:
    """10원 미만 버림."""
    return int(x // 10) * 10


def social_insurance(total_pay: int) -> dict:
    """근로자 부담 4대보험 연액. 월 보수 = 총급여 / 12."""
    monthly = F(total_pay, 12)
    base = int(monthly // 1000) * 1000                      # 기준소득월액: 천 원 미만 버림
    base = min(max(base, C.PENSION_BASE_MIN), C.PENSION_BASE_MAX)
    pension = floor10(base * C.PENSION_RATE)
    health = floor10(monthly * C.HEALTH_RATE)
    ltc = floor10(health * C.LTC_RATIO)
    employ = floor10(monthly * C.EMPLOY_RATE)
    return {"pension": pension * 12, "health": health * 12, "ltc": ltc * 12, "employ": employ * 12}


def wage_income_deduction(total_pay: int) -> F:
    """근로소득공제 (한도 2,000만 원)."""
    t = total_pay
    if t <= 5_000_000:
        d = t * F(70, 100)
    elif t <= 15_000_000:
        d = 3_500_000 + (t - 5_000_000) * F(40, 100)
    elif t <= 45_000_000:
        d = 7_500_000 + (t - 15_000_000) * F(15, 100)
    elif t <= 100_000_000:
        d = 12_000_000 + (t - 45_000_000) * F(5, 100)
    else:
        d = 14_750_000 + (t - 100_000_000) * F(2, 100)
    return min(F(d), F(20_000_000))


def income_tax(tax_base) -> F:
    """산출세액. 구간별 초과분에만 세율을 적용한다."""
    tax, prev = F(0), 0
    for cap, rate in C.TAX_BRACKETS:
        if tax_base <= prev:
            break
        upper = tax_base if cap is None else min(tax_base, cap)
        tax += (upper - prev) * rate
        if cap is None:
            break
        prev = cap
    return tax


def wage_tax_credit(calc_tax, total_pay: int) -> F:
    """근로소득세액공제 (소득세법 제59조). 감면 조정 전 금액."""
    if calc_tax <= 1_300_000:
        credit = calc_tax * F(55, 100)
    else:
        credit = 715_000 + (calc_tax - 1_300_000) * F(30, 100)
    if total_pay <= 33_000_000:
        limit = F(740_000)
    elif total_pay <= 70_000_000:
        limit = max(740_000 - (total_pay - 33_000_000) * F(8, 1000), F(660_000))
    elif total_pay <= 120_000_000:
        limit = max(660_000 - (total_pay - 70_000_000) * F(1, 2), F(500_000))
    else:
        limit = max(500_000 - (total_pay - 120_000_000) * F(1, 2), F(200_000))
    return min(F(credit), limit)


def calc_net_pay(annual_salary: int, non_taxable_monthly: int = C.DEFAULT_NON_TAXABLE_MONTHLY,
                 relief: bool = False) -> NetPay:
    """relief=True 면 중소기업 취업 청년 감면(90%, 한도 200만 원)을 적용한다."""
    if annual_salary <= 0:
        raise ValueError("연봉은 0보다 커야 한다")
    non_taxable_annual = non_taxable_monthly * 12
    if non_taxable_monthly < 0 or non_taxable_annual >= annual_salary:
        raise ValueError("비과세 금액이 연봉 범위를 벗어났다")

    total_pay = annual_salary - non_taxable_annual
    ins = social_insurance(total_pay)
    insurance = sum(ins.values())
    wage_income = total_pay - wage_income_deduction(total_pay)

    def settle(use_insurance_deduction: bool) -> dict:
        deduction = C.BASIC_DEDUCTION + ins["pension"]
        if use_insurance_deduction:                         # 가 경로: 건강·장기요양·고용 보험료 특별소득공제
            deduction += ins["health"] + ins["ltc"] + ins["employ"]
        tax_base = max(wage_income - deduction, F(0))
        calc_tax = income_tax(tax_base)
        relief_tax = min(calc_tax * C.RELIEF_RATE_YOUTH, F(C.RELIEF_CAP)) if relief else F(0)
        credit = wage_tax_credit(calc_tax, total_pay)
        if calc_tax > 0:                                    # 시행령 제27조 제9항
            credit = credit * (1 - relief_tax / calc_tax)
        std = 0 if use_insurance_deduction else C.STANDARD_TAX_CREDIT   # 나 경로: 표준세액공제
        final_tax = max(calc_tax - relief_tax - credit - std, F(0))
        return {"tax_base": tax_base, "calc_tax": calc_tax, "relief_tax": relief_tax, "credit": credit,
                "std": std, "final_tax": final_tax,
                "option": "insurance_deduction" if use_insurance_deduction else "standard_credit"}

    a, b = settle(True), settle(False)
    best = a if a["final_tax"] <= b["final_tax"] else b     # 근로자에게 유리한 쪽. 같으면 가 경로
    final_tax = math.floor(best["final_tax"])
    local_tax = math.floor(final_tax * C.LOCAL_TAX_RATE)
    net = annual_salary - insurance - final_tax - local_tax
    return NetPay(
        annual_salary=annual_salary, non_taxable_annual=non_taxable_annual, total_pay=total_pay,
        pension=ins["pension"], health=ins["health"], ltc=ins["ltc"], employ=ins["employ"], insurance=insurance,
        wage_income=math.floor(wage_income), tax_base=math.floor(best["tax_base"]),
        calc_tax=math.floor(best["calc_tax"]), relief_tax=math.floor(best["relief_tax"]),
        wage_credit=math.floor(best["credit"]), standard_credit=best["std"],
        final_tax=final_tax, local_tax=local_tax, net_annual=net, net_monthly_avg=net // 12,
        option=best["option"],
    )
