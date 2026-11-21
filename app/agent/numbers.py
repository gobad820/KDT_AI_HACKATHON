"""설명용 값 목록과 숫자 검증기 (docs/agent-spec.md 8장).

LLM 은 이 목록의 label 표기만 쓴다. 설명문 속 숫자는 코드가 목록과 대조한다.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from app.schemas import CompareCore

SCENARIO_NAMES = {"none": "감면 없음", "current_law": "현행법", "proposal_base": "정부안(우대지역 아님)",
                  "proposal_pref": "정부안(우대지역으로 지정될 때)"}

# 고정 허용: 연수, 유형 번호, 감면율, 한도, 연도, 나이 기준, 개월
ALLOWED_YEARS_COUNT = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12}
ALLOWED_PLAIN = {2026, 2027, 2029, 15, 34, 90, 30, 6, 12} | ALLOWED_YEARS_COUNT
ALLOWED_MAN = {200, 1000}                      # 감면 한도 200만 원, 보증금 기준 1,000만 원


def man(won: int) -> int:
    return int(round(won / 10_000))


def label(won: int, exact: bool = False) -> str:
    return f"{man(won):,}만 원" if exact else f"약 {man(won):,}만 원"


def build_value_list(core: CompareCore) -> List[dict]:
    names = core.company_names
    vals: List[dict] = []

    def add(name: str, won: int, exact: bool = False):
        vals.append({"name": name, "won": int(won), "label": label(won, exact)})

    jobs = {j.id: j for j in core.jobs}
    for jid, job in jobs.items():
        n = names.get(jid, f"공고 {jid}")
        if jid in core.annual_salaries:
            add(f"{n} 연봉", core.annual_salaries[jid], exact=True)
        add(f"{n} 세후 연봉(감면 없음)", job.pay.none.net_annual)
        add(f"{n} 세후 연봉(감면 적용)", job.pay.with_relief.net_annual)
        add(f"{n} 세후 월평균(감면 없음)", job.pay.none.net_monthly_avg)
        add(f"{n} 월 주거비", job.housing_monthly)
        add(f"{n} 연 주거비", job.housing_monthly * 12)
        if job.rent is not None:
            add(f"{n} 월세 25% 지점", job.rent.p25)
            add(f"{n} 월세 75% 지점", job.rent.p75)
        for s in job.scenarios:
            sn = SCENARIO_NAMES[s.id]
            add(f"{n} {sn} 누적 남는 돈", s.cumulative_remaining)
            add(f"{n} {sn} 1년차 남는 돈", s.first_year_remaining)
            if s.relief_total:
                add(f"{n} {sn} 감면액 합계", s.relief_total)
        add(f"{n} 연 감면 효과", job.pay.with_relief.net_annual - job.pay.none.net_annual)
    if len(jobs) == 2:
        a, b = sorted(jobs)
        ja, jb = jobs[a], jobs[b]
        if a in core.annual_salaries and b in core.annual_salaries:
            add("연봉 차이", abs(core.annual_salaries[a] - core.annual_salaries[b]), exact=True)
        add("월 주거비 차이", abs(ja.housing_monthly - jb.housing_monthly))
        add("연 주거비 차이", abs(ja.housing_monthly - jb.housing_monthly) * 12)
        add("세후 연봉 차이(감면 없음)", abs(ja.pay.none.net_annual - jb.pay.none.net_annual))
    for c in core.comparison:
        sn = SCENARIO_NAMES[c.scenario_id]
        add(f"{sn} 누적 차이", c.difference)
        if c.break_even:
            add(f"{sn} 손익분기 연봉({names.get(c.break_even.job_id, c.break_even.job_id)})",
                c.break_even.annual_salary, exact=True)
    return vals


NUM = r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?"
MONEY = re.compile(rf"(?:({NUM})\s*억\s*)?(?:({NUM})\s*만)?\s*원|({NUM})\s*억(?!\s*\d)")
OTHER = re.compile(rf"({NUM})")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def verify_numbers(text: str, values: List[dict]) -> Tuple[bool, List[str]]:
    """목록에 없는 숫자 표현을 돌려준다. 만 원 표기는 만 원 단위로, 원 표기는 원 단위로 대조한다."""
    man_allowed = {man(v["won"]) for v in values} | ALLOWED_MAN
    won_allowed = {v["won"] for v in values}
    bad: List[str] = []
    rest = text
    for m in MONEY.finditer(text):
        eok, manv, eok_only = m.group(1), m.group(2), m.group(3)
        token = m.group(0)
        if eok_only:
            ok = _num(eok_only) * 10_000 in man_allowed
        elif eok or manv:
            total = (_num(eok) * 10_000 if eok else 0) + (_num(manv) if manv else 0)
            ok = total in man_allowed
        else:
            continue                                    # '원'만 걸린 경우: 숫자는 아래에서 원 단위로 대조
        if not ok:
            bad.append(token.strip())
        rest = rest.replace(m.group(0), " ", 1)
    for m in OTHER.finditer(rest):
        v = _num(m.group(1))
        if v in ALLOWED_PLAIN or v in man_allowed or v in won_allowed:
            continue
        bad.append(m.group(1))
    return (not bad), bad
