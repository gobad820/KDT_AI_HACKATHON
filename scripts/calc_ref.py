"""남는 돈 비교 - 계산 규칙 참고 구현 (대조용)

- docs/calc-rules.md 의 단계를 그대로 옮긴 것. 서비스 코드(app/calc)와 따로 짠 대조용이다.
- 공식 계산기(국세청 연말정산 모의계산, 4대보험 계산기)와 대조하기 전이다.
- Claude 가 작성했다. 팀이 직접 검토, 수정, 검증하고 AI 활용내역에 적는다.
- 금액 단위는 원. 1인 가구, 근로소득만 있는 사람, 연중 12개월 근무를 가정한다.
- 비율은 분수(Fraction)로 계산한다. 부동소수점으로 계산하면 10원 미만 버림에서 오차가 난다
  (예: 월 보수 2,966,666.67원 x 0.9% 는 정확히 26,700원인데 float 로는 26,699.99... 가 되어 26,690원으로 버려진다).

실행: python3 scripts/calc_ref.py
"""
import math
from fractions import Fraction as F

# ---- 상수 (2026년 기준, 출처와 확인 상태는 docs/calc-rules.md 2장) ----
PENSION_RATE = F(475, 10000)         # 국민연금 근로자 부담 4.75%
PENSION_BASE_MAX = 6_590_000         # 기준소득월액 상한 (2026.7 ~ 2027.6)
PENSION_BASE_MIN = 410_000           # 기준소득월액 하한
HEALTH_RATE = F(3595, 100000)        # 건강보험 근로자 부담 3.595%
LTC_RATE_OF_HEALTH = F(9448, 71900)  # 장기요양 = 건강보험료 x (0.9448% / 7.19%)
EMPLOY_RATE = F(9, 1000)             # 고용보험 근로자 부담 0.9%
BASIC_DEDUCTION = 1_500_000          # 본인 기본공제
STANDARD_TAX_CREDIT = 130_000        # 표준세액공제
RELIEF_RATE_YOUTH = F(90, 100)       # 중소기업 취업 청년 감면율
RELIEF_CAP = 2_000_000               # 과세기간별 감면 한도
LOCAL_TAX_RATE = F(10, 100)          # 지방소득세

TAX_BRACKETS = [                     # (과세표준 상한, 세율)
    (14_000_000, F(6, 100)), (50_000_000, F(15, 100)), (88_000_000, F(24, 100)),
    (150_000_000, F(35, 100)), (300_000_000, F(38, 100)), (500_000_000, F(40, 100)),
    (1_000_000_000, F(42, 100)), (None, F(45, 100)),
]

# 정부안(2026.8) 지역 유형별 청년 감면기간(년). 국회 확정 전.
RELIEF_YEARS_BY_TYPE = {1: 5, 2: 6, 3: 7, 4: 10}
CURRENT_LAW_YEARS = 5
CURRENT_LAW_LAST_HIRE_YEAR = 2026    # 현행법: 2026.12.31 까지 취업분


def floor10(x):
    return int(x // 10) * 10


def social_insurance(total_pay):
    """총급여에 대한 근로자 부담 4대보험. 연액으로 돌려준다. 월 보수 = 총급여 / 12."""
    monthly_pay = F(total_pay, 12)
    pension_base = min(max(int(monthly_pay // 1000) * 1000, PENSION_BASE_MIN), PENSION_BASE_MAX)
    pension = floor10(pension_base * PENSION_RATE)
    health = floor10(monthly_pay * HEALTH_RATE)
    ltc = floor10(health * LTC_RATE_OF_HEALTH)
    employ = floor10(monthly_pay * EMPLOY_RATE)
    return {"pension": pension * 12, "health": health * 12, "ltc": ltc * 12, "employ": employ * 12}


def wage_income_deduction(total_pay):
    if total_pay <= 5_000_000:
        d = total_pay * F(70, 100)
    elif total_pay <= 15_000_000:
        d = 3_500_000 + (total_pay - 5_000_000) * F(40, 100)
    elif total_pay <= 45_000_000:
        d = 7_500_000 + (total_pay - 15_000_000) * F(15, 100)
    elif total_pay <= 100_000_000:
        d = 12_000_000 + (total_pay - 45_000_000) * F(5, 100)
    else:
        d = 14_750_000 + (total_pay - 100_000_000) * F(2, 100)
    return min(F(d), F(20_000_000))


def income_tax(tax_base):
    tax, prev = F(0), 0
    for cap, rate in TAX_BRACKETS:
        if tax_base <= prev:
            break
        upper = tax_base if cap is None else min(tax_base, cap)
        tax += (upper - prev) * rate
        if cap is None:
            break
        prev = cap
    return tax


def wage_tax_credit(calc_tax, total_pay):
    """근로소득세액공제 (소득세법 59조 1항, 2항). 감면 조정 전 금액."""
    credit = calc_tax * F(55, 100) if calc_tax <= 1_300_000 else 715_000 + (calc_tax - 1_300_000) * F(30, 100)
    if total_pay <= 33_000_000:
        limit = F(740_000)
    elif total_pay <= 70_000_000:
        limit = max(740_000 - (total_pay - 33_000_000) * F(8, 1000), F(660_000))
    elif total_pay <= 120_000_000:
        limit = max(660_000 - (total_pay - 70_000_000) * F(1, 2), F(500_000))
    else:
        limit = max(500_000 - (total_pay - 120_000_000) * F(1, 2), F(200_000))
    return min(F(credit), limit)


def calc_net_pay(annual_salary, nontax_monthly=200_000, relief=False):
    """연봉 -> 연간 세후 금액. relief=True 면 중소기업 취업 청년 감면을 적용한다."""
    nontax_annual = nontax_monthly * 12
    total_pay = annual_salary - nontax_annual                   # 총급여
    ins = social_insurance(total_pay)
    insurance = sum(ins.values())
    wage_income = total_pay - wage_income_deduction(total_pay)  # 근로소득금액

    def settle(use_insurance_deduction):
        deduction = BASIC_DEDUCTION + ins["pension"]
        if use_insurance_deduction:                             # 특별소득공제(건강, 장기요양, 고용)
            deduction += ins["health"] + ins["ltc"] + ins["employ"]
        tax_base = max(wage_income - deduction, F(0))
        calc_tax = income_tax(tax_base)                         # 산출세액
        relief_tax = min(calc_tax * RELIEF_RATE_YOUTH, F(RELIEF_CAP)) if relief else F(0)
        credit = wage_tax_credit(calc_tax, total_pay)
        if calc_tax > 0:                                        # 조특령 27조 9항
            credit = credit * (1 - relief_tax / calc_tax)
        std = 0 if use_insurance_deduction else STANDARD_TAX_CREDIT
        final_tax = max(calc_tax - relief_tax - credit - std, F(0))
        return {"tax_base": tax_base, "calc_tax": calc_tax, "relief_tax": relief_tax,
                "wage_credit": credit, "standard_credit": std, "final_tax": final_tax,
                "option": "insurance_deduction" if use_insurance_deduction else "standard_credit"}

    a, b = settle(True), settle(False)
    best = a if a["final_tax"] <= b["final_tax"] else b        # 근로자에게 유리한 쪽
    final_tax = math.floor(best["final_tax"])
    local_tax = math.floor(final_tax * LOCAL_TAX_RATE)
    net = annual_salary - insurance - final_tax - local_tax
    return {
        "annual_salary": annual_salary, "nontax_annual": nontax_annual, "total_pay": total_pay,
        "insurance": insurance, "insurance_detail": ins,
        "wage_income": math.floor(wage_income), "tax_base": math.floor(best["tax_base"]),
        "calc_tax": math.floor(best["calc_tax"]), "relief_tax": math.floor(best["relief_tax"]),
        "wage_credit": math.floor(best["wage_credit"]), "standard_credit": best["standard_credit"],
        "final_tax": final_tax, "local_tax": local_tax,
        "net_annual": net, "net_monthly_avg": net // 12, "option": best["option"],
    }


def relief_years(scenario, region_type, hire_year):
    """시나리오별 감면 적용 연수. region_type 은 정부안의 1~4유형."""
    if scenario == "none":
        return 0
    if scenario == "current_law":
        return CURRENT_LAW_YEARS if hire_year <= CURRENT_LAW_LAST_HIRE_YEAR else 0
    if scenario == "proposal":
        return RELIEF_YEARS_BY_TYPE[region_type]
    raise ValueError(scenario)


def simulate(annual_salary, rent_monthly, years_with_relief, horizon, nontax_monthly=200_000):
    """연차별 남는 돈(세후 연봉 - 월세 x 12)과 누적. 연봉, 요율, 월세는 고정으로 가정한다."""
    with_relief = calc_net_pay(annual_salary, nontax_monthly, relief=True)
    without = calc_net_pay(annual_salary, nontax_monthly, relief=False)
    housing = rent_monthly * 12
    yearly, cumulative = [], 0
    for year in range(1, horizon + 1):
        applied = year <= years_with_relief
        net = (with_relief if applied else without)["net_annual"]
        cumulative += net - housing
        yearly.append({"year": year, "relief_applied": applied, "net_annual": net,
                       "housing_annual": housing, "remaining": net - housing, "cumulative": cumulative})
    relief_total = (with_relief["net_annual"] - without["net_annual"]) * min(years_with_relief, horizon)
    return {"yearly": yearly, "cumulative": cumulative, "relief_total": relief_total,
            "first_year": with_relief if years_with_relief > 0 else without}


def break_even_salary(target_cumulative, rent_monthly, years_with_relief, horizon, nontax_monthly=200_000):
    """누적 남는 돈이 target_cumulative 이상이 되는 가장 낮은 연봉(만 원 단위). 범위 밖이면 None."""
    def cum(k):
        return simulate(k * 10_000, rent_monthly, years_with_relief, horizon, nontax_monthly)["cumulative"]

    lo, hi = 1_500, 30_000                                     # 1,500만 원 ~ 3억 원
    if cum(hi) < target_cumulative:
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if cum(mid) >= target_cumulative:
            hi = mid
        else:
            lo = mid + 1
    return lo * 10_000


if __name__ == "__main__":
    won = lambda v: f"{v:,}"
    print("[1] 연봉별 세후 (비과세 식대 월 20만 원 가정)")
    print("연봉 | 4대보험 | 과세표준 | 산출세액 | 결정세액 | 지방소득세 | 연 세후 | 월평균 || 결정세액(감면) | 연 세후(감면) | 연 감면효과")
    for s in (26_000_000, 28_000_000, 30_000_000, 33_000_000, 36_000_000, 38_000_000, 40_000_000,
              45_000_000, 55_000_000, 70_000_000):
        n, r = calc_net_pay(s), calc_net_pay(s, relief=True)
        print(" | ".join([won(s), won(n["insurance"]), won(n["tax_base"]), won(n["calc_tax"]), won(n["final_tax"]),
                          won(n["local_tax"]), won(n["net_annual"]), won(n["net_monthly_avg"]), "",
                          won(r["final_tax"]), won(r["net_annual"]), won(r["net_annual"] - n["net_annual"])]))

    print("\n[2] 4대보험 내역 (연액)")
    for s in (33_000_000, 38_000_000):
        print(won(s), calc_net_pay(s)["insurance_detail"])

    print("\n[3] 감면기간별 누적 효과 (연봉 고정)")
    for s in (28_000_000, 33_000_000, 38_000_000, 45_000_000):
        eff = calc_net_pay(s, relief=True)["net_annual"] - calc_net_pay(s)["net_annual"]
        print(won(s), "연", won(eff), "|", ", ".join(f"{y}년 {won(eff * y)}" for y in (5, 6, 7, 10)))

    print("\n[4] 예시 비교 (월세는 설명용 임의값)")
    A = {"salary": 38_000_000, "rent": 850_000, "type_base": 1, "type_pref": 2}   # 수도권
    B = {"salary": 34_000_000, "rent": 450_000, "type_base": 2, "type_pref": 3}   # 비수도권 광역시
    cases = {"none": (0, 0),
             "current_law(2027 입사)": (relief_years("current_law", 1, 2027), relief_years("current_law", 2, 2027)),
             "proposal_base": (relief_years("proposal", A["type_base"], 2027), relief_years("proposal", B["type_base"], 2027)),
             "proposal_pref": (relief_years("proposal", A["type_pref"], 2027), relief_years("proposal", B["type_pref"], 2027))}
    for horizon in (5, 10):
        for name, (ya, yb) in cases.items():
            a = simulate(A["salary"], A["rent"], ya, horizon)
            b = simulate(B["salary"], B["rent"], yb, horizon)
            better = "A" if a["cumulative"] >= b["cumulative"] else "B"
            if better == "B":
                be = ("A", break_even_salary(b["cumulative"], A["rent"], ya, horizon))
            else:
                be = ("B", break_even_salary(a["cumulative"], B["rent"], yb, horizon))
            print(f"{horizon}년 {name}: A({ya}년) 1년차 {won(a['yearly'][0]['remaining'])} 누적 {won(a['cumulative'])} 감면합 {won(a['relief_total'])}"
                  f" / B({yb}년) 1년차 {won(b['yearly'][0]['remaining'])} 누적 {won(b['cumulative'])} 감면합 {won(b['relief_total'])}"
                  f" / 더 남는 쪽 {better} 차이 {won(abs(a['cumulative'] - b['cumulative']))} / 손익분기 {be[0]} {won(be[1]) if be[1] else '범위 밖'}")
