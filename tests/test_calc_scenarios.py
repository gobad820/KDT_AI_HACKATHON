"""시나리오, 누적, 손익분기. 예시 쌍은 docs/calc-rules.md 7장 (월세는 설명용 임의값)."""
import pytest

from app.calc.scenarios import SimJob, break_even_salary, relief_years, simulate

A = SimJob("A", 38_000_000, 200_000, 850_000, 1, 2, True)      # 수도권
B = SimJob("B", 34_000_000, 200_000, 450_000, 2, 3, True)      # 비수도권 광역시

# horizon, 시나리오, A 감면 연수, A 누적, B 감면 연수, B 누적, 더 남는 쪽, 차이, 손익분기(A)
ROWS = [
    (5, "none", 0, 116_049_030, 0, 124_441_480, "B", 8_392_450, 40_190_000),
    (5, "current_law", 0, 116_049_030, 0, 124_441_480, "B", 8_392_450, 40_190_000),
    (5, "proposal_base", 5, 121_705_600, 6, 127_649_000, "B", 5_943_400, 39_340_000),
    (5, "proposal_pref", 6, 121_705_600, 7, 127_649_000, "B", 5_943_400, 39_340_000),
    (10, "none", 0, 232_098_060, 0, 248_882_960, "B", 16_784_900, 40_190_000),
    (10, "current_law", 0, 232_098_060, 0, 248_882_960, "B", 16_784_900, 40_190_000),
    (10, "proposal_base", 5, 237_754_630, 6, 252_731_984, "B", 14_977_354, 39_810_000),
    (10, "proposal_pref", 6, 238_885_944, 7, 253_373_488, "B", 14_487_544, 39_730_000),
]


@pytest.mark.parametrize("horizon,sid,ya,cum_a,yb,cum_b,better,diff,be", ROWS)
def test_example_pair(horizon, sid, ya, cum_a, yb, cum_b, better, diff, be):
    res = simulate([A, B], 2027, horizon)
    sa = next(s for s in res.scenarios["A"] if s.id == sid)
    sb = next(s for s in res.scenarios["B"] if s.id == sid)
    cmp_ = next(c for c in res.comparison if c.scenario_id == sid)
    assert (sa.relief_years, sa.cumulative_remaining) == (ya, cum_a)
    assert (sb.relief_years, sb.cumulative_remaining) == (yb, cum_b)
    assert (cmp_.better_job_id, cmp_.difference) == (better, diff)
    assert (cmp_.break_even.job_id, cmp_.break_even.annual_salary) == ("A", be)


def test_pay_and_yearly_rows():
    res = simulate([A, B], 2027, 10)
    assert res.pay["A"].none.net_annual == 33_409_806 and res.pay["A"].with_relief.net_annual == 34_541_120
    assert res.pay["B"].none.net_annual == 30_288_296 and res.pay["B"].with_relief.net_annual == 30_929_800
    s = next(s for s in res.scenarios["A"] if s.id == "proposal_base")
    assert len(s.yearly) == 10
    assert (s.yearly[4].relief_applied, s.yearly[4].cumulative) == (True, 121_705_600)
    assert (s.yearly[5].relief_applied, s.yearly[5].cumulative) == (False, 144_915_406)
    assert s.relief_total == 5_656_570 and s.first_year_remaining == 24_341_120


def test_relief_years_rules():
    assert relief_years("none", A, 2027) == 0
    assert relief_years("current_law", A, 2026) == 5 and relief_years("current_law", A, 2027) == 0
    assert relief_years("proposal_base", A, 2027) == 5 and relief_years("proposal_pref", A, 2027) == 6
    other = SimJob("B", 30_000_000, 200_000, 400_000, 3, 4, True)
    assert relief_years("proposal_base", other, 2027) == 7 and relief_years("proposal_pref", other, 2027) == 10
    not_eligible = SimJob("A", 38_000_000, 200_000, 850_000, 1, 2, False)
    assert all(relief_years(s, not_eligible, 2026) == 0 for s in ("none", "current_law", "proposal_base", "proposal_pref"))


def test_hire_year_2026_current_law_applies():
    res = simulate([A, B], 2026, 5)
    sa = next(s for s in res.scenarios["A"] if s.id == "current_law")
    assert sa.relief_years == 5 and sa.cumulative_remaining == 121_705_600


def test_tie_and_unreachable():
    same = SimJob("B", 38_000_000, 200_000, 850_000, 1, 2, True)
    res = simulate([A, same], 2027, 5)
    assert all(c.better_job_id == "A" and c.difference == 0 and c.break_even is None for c in res.comparison)
    assert break_even_salary(10 ** 12, A, 0, 5) is None            # 도달할 수 없는 목표


def test_same_salary_difference_is_housing_only():
    x = SimJob("A", 35_000_000, 200_000, 700_000, 1, 2, True)
    y = SimJob("B", 35_000_000, 200_000, 500_000, 1, 2, True)
    res = simulate([x, y], 2027, 5)
    assert all(c.better_job_id == "B" and c.difference == 200_000 * 12 * 5 for c in res.comparison)
