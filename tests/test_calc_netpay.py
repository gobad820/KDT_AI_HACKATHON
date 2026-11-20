"""세후 계산. 기대값은 scripts/calc_ref.py(따로 짠 참고 구현)의 출력이다.
공식 계산기와 대조한 값이 아니다. docs/calc-rules.md 8장의 대조가 끝나면 이 표를 그 값으로 바꾼다."""
from fractions import Fraction as F

import pytest

from app.calc.netpay import (calc_net_pay, income_tax, social_insurance, wage_income_deduction, wage_tax_credit)

# 연봉, 4대보험, 결정세액, 지방소득세, 세후 연봉, 월평균, 감면 시 세후 연봉
TABLE = [
    (26_000_000, 2_292_840, 199_114, 19_911, 23_488_135, 1_957_344, 23_707_160),
    (28_000_000, 2_487_240, 242_445, 24_244, 25_246_071, 2_103_839, 25_512_760),
    (30_000_000, 2_681_880, 342_432, 34_243, 26_941_445, 2_245_120, 27_318_120),
    (33_000_000, 2_973_360, 532_348, 53_234, 29_441_058, 2_453_421, 30_026_640),
    (36_000_000, 3_264_960, 786_556, 78_655, 31_869_829, 2_655_819, 32_735_040),
    (38_000_000, 3_458_880, 1_028_468, 102_846, 33_409_806, 2_784_150, 34_541_120),
    (40_000_000, 3_653_400, 1_270_290, 127_029, 34_949_281, 2_912_440, 36_297_653),
    (45_000_000, 4_139_400, 1_874_890, 187_489, 38_798_221, 3_233_185, 40_423_365),
    (55_000_000, 5_111_040, 3_121_344, 312_134, 46_455_482, 3_871_290, 48_271_492),
    (70_000_000, 6_568_560, 5_040_216, 504_021, 57_887_203, 4_823_933, 59_832_476),
]


@pytest.mark.parametrize("salary,insurance,final_tax,local_tax,net,monthly,net_relief", TABLE)
def test_table(salary, insurance, final_tax, local_tax, net, monthly, net_relief):
    n = calc_net_pay(salary)
    assert (n.insurance, n.final_tax, n.local_tax, n.net_annual, n.net_monthly_avg) == (
        insurance, final_tax, local_tax, net, monthly)
    assert calc_net_pay(salary, relief=True).net_annual == net_relief


def test_wage_income_deduction_boundaries():
    assert wage_income_deduction(5_000_000) == 3_500_000
    assert wage_income_deduction(15_000_000) == 7_500_000
    assert wage_income_deduction(45_000_000) == 12_000_000
    assert wage_income_deduction(100_000_000) == 14_750_000
    assert wage_income_deduction(400_000_000) == 20_000_000      # 한도


def test_income_tax_boundaries():
    assert income_tax(14_000_000) == 840_000
    assert income_tax(50_000_000) == 6_240_000
    assert income_tax(88_000_000) == 15_360_000
    assert income_tax(150_000_000) == 37_060_000
    assert income_tax(0) == 0


def test_wage_tax_credit_formula_and_limits():
    assert wage_tax_credit(F(1_000_000), 30_000_000) == 550_000
    assert wage_tax_credit(F(1_300_000), 30_000_000) == 715_000
    big = F(10_000_000)                                          # 식으로는 한도를 넘는 산출세액
    assert wage_tax_credit(big, 33_000_000) == 740_000
    assert wage_tax_credit(big, 43_000_000) == 660_000
    assert wage_tax_credit(big, 70_200_000) == 560_000
    assert wage_tax_credit(big, 71_000_000) == 500_000
    assert wage_tax_credit(big, 120_400_000) == 300_000
    assert wage_tax_credit(big, 121_000_000) == 200_000


def test_social_insurance_monthly_and_pension_bounds():
    ins = social_insurance(2_550_000 * 12)
    assert (ins["pension"], ins["health"], ins["ltc"], ins["employ"]) == (121_120 * 12, 91_670 * 12, 12_040 * 12, 22_950 * 12)
    assert social_insurance(7_000_000 * 12)["pension"] == 313_020 * 12   # 상한 659만 원
    assert social_insurance(300_000 * 12)["pension"] == 19_470 * 12      # 하한 41만 원


def test_no_float_error_in_floor():
    # 월 보수 2,966,666.67원 x 0.9% 는 정확히 26,700원이다. float 로 계산하면 26,690원으로 버려진다.
    assert calc_net_pay(38_000_000).employ == 26_700 * 12


def test_path_selection():
    n = calc_net_pay(33_000_000)
    assert (n.final_tax, n.option) == (532_348, "insurance_deduction")
    r = calc_net_pay(33_000_000, relief=True)
    assert (r.final_tax, r.option, r.relief_tax) == (0, "standard_credit", 1_269_885)


def test_relief_cap():
    r = calc_net_pay(45_000_000, relief=True)
    assert (r.calc_tax, r.relief_tax, r.wage_credit, r.final_tax) == (2_538_090, 2_000_000, 140_602, 397_487)


def test_nts_guide_example():
    # 국세청 「중소기업 취업자 소득세 감면제도 안내」(2024.8) 사례: 산출세액 1,762,500원
    calc_tax = F(1_762_500)
    credit = wage_tax_credit(calc_tax, 36_000_000)
    assert credit == 716_000
    assert calc_tax * F(90, 100) == 1_586_250
    assert credit * (1 - F(90, 100)) == 71_600
    assert calc_tax * F(70, 100) == 1_233_750 and credit * (1 - F(70, 100)) == 214_800


def test_invalid_input():
    with pytest.raises(ValueError):
        calc_net_pay(0)
    with pytest.raises(ValueError):
        calc_net_pay(2_000_000, non_taxable_monthly=200_000)
