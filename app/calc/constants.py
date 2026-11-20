"""계산 상수 (2026년). 값과 출처, 확인 상태는 docs/calc-rules.md 2장. 값을 바꾸면 그 표도 같이 고친다.

비율은 부동소수점 오차가 없도록 분수(Fraction)로 둔다.
"""
from __future__ import annotations

from fractions import Fraction as F

RULES_VERSION = "2026-v1"

# 4대보험 근로자 부담 [2차: 공단 고시 원문 재확인 필요]
PENSION_RATE = F(475, 10_000)            # 국민연금 4.75%
PENSION_BASE_MAX = 6_590_000             # 기준소득월액 상한 (2026.7 ~ 2027.6)
PENSION_BASE_MIN = 410_000               # 기준소득월액 하한
HEALTH_RATE = F(3_595, 100_000)          # 건강보험 3.595%
LTC_RATIO = F(9_448, 71_900)             # 장기요양 = 건강보험료 x (0.9448% / 7.19%)
EMPLOY_RATE = F(9, 1_000)                # 고용보험 0.9%

# 소득세 [2차: 소득세법 원문 재확인 필요]
BASIC_DEDUCTION = 1_500_000              # 본인 기본공제
STANDARD_TAX_CREDIT = 130_000            # 표준세액공제
LOCAL_TAX_RATE = F(10, 100)              # 지방소득세
TAX_BRACKETS = [                         # (과세표준 상한, 세율). None 은 상한 없음
    (14_000_000, F(6, 100)), (50_000_000, F(15, 100)), (88_000_000, F(24, 100)),
    (150_000_000, F(35, 100)), (300_000_000, F(38, 100)), (500_000_000, F(40, 100)),
    (1_000_000_000, F(42, 100)), (None, F(45, 100)),
]

# 중소기업 취업자 소득세 감면 (조세특례제한법 제30조, 시행령 제27조)
RELIEF_RATE_YOUTH = F(90, 100)           # 청년 감면율 [2차]
RELIEF_CAP = 2_000_000                   # 과세기간별 한도 [확인: 시행령 제27조 제8항]
CURRENT_LAW_YEARS = 5                    # 현행법 청년 감면기간 [2차]
CURRENT_LAW_LAST_HIRE_YEAR = 2026        # 현행법은 2026.12.31 까지 취업분 [2차]
RELIEF_YEARS_BY_TYPE = {1: 5, 2: 6, 3: 7, 4: 10}   # 정부안(2026.8) 유형별 청년 감면기간 [2차, 국회 확정 전]

# 그 밖
DEFAULT_NON_TAXABLE_MONTHLY = 200_000    # 식대 비과세 월 20만 원 [2차]
MIN_WAGE_ANNUAL = 25_882_560             # 시급 10,320원 x 209시간 x 12 [2차]
BREAK_EVEN_MIN = 15_000_000              # 손익분기 탐색 범위
BREAK_EVEN_MAX = 300_000_000
