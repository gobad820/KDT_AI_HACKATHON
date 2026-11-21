"""EXPLAIN: 계산 결과 -> 설명문. 숫자는 설명용 값 목록의 표기만 쓰고 코드가 대조한다.

LLM 이 없거나 실패하거나 숫자 검증을 두 번 통과하지 못하면 템플릿 문장을 쓴다(ai_generated=False).
Profile 은 받지 않는다. 고지 문구는 서버가 notices 로 붙인다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app import config
from app.schemas import CompareCore, Explanation

from .llm import LLMClient
from .numbers import SCENARIO_NAMES, build_value_list, label, verify_numbers

PROMPT_VERSION = "explain_v1"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")
SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}


def base_scenario(core: CompareCore) -> str:
    """결론의 기준. 확정된 제도인 현행법, 대상 아닐 가능성이 높은 공고가 있으면 감면 없음."""
    if any(j.eligibility.status == "unlikely" for j in core.jobs):
        return "none"
    return "current_law"


def _cmp(core: CompareCore, sid: str):
    return next(c for c in core.comparison if c.scenario_id == sid)


def template_explanation(core: CompareCore) -> str:
    names = core.company_names
    nm = lambda jid: names.get(jid, f"공고 {jid}")
    jobs = {j.id: j for j in core.jobs}
    base = base_scenario(core)
    c = _cmp(core, base)
    h = core.horizon_years
    base_label = "감면 없음 기준" if base == "none" or core.hire_year >= 2027 else "현행법 기준"
    parts = []
    if c.difference == 0:
        parts.append(f"{h}년 동안 세금과 주거비를 빼면 두 공고에 남는 돈이 같습니다({base_label}).")
    else:
        parts.append(f"{h}년 동안 세금과 주거비를 빼면 {nm(c.better_job_id)} 쪽이 {label(c.difference)} 더 남습니다({base_label}).")

    if len(jobs) == 2:
        a, b = sorted(jobs)
        ja, jb = jobs[a], jobs[b]
        net_hi = a if ja.pay.none.net_annual >= jb.pay.none.net_annual else b
        house_hi = a if ja.housing_monthly >= jb.housing_monthly else b
        net_diff = abs(ja.pay.none.net_annual - jb.pay.none.net_annual)
        house_diff = abs(ja.housing_monthly - jb.housing_monthly) * 12
        if net_diff and house_diff:
            parts.append(f"세후 연봉은 {nm(net_hi)} 쪽이 1년에 {label(net_diff)} 많고, "
                         f"주거비는 {nm(house_hi)} 쪽이 1년에 {label(house_diff)} 더 듭니다.")
        elif net_diff:
            parts.append(f"주거비는 같고 세후 연봉이 {nm(net_hi)} 쪽이 1년에 {label(net_diff)} 많습니다.")
        elif house_diff:
            parts.append(f"세후 연봉은 같고 주거비가 {nm(house_hi)} 쪽이 1년에 {label(house_diff)} 더 듭니다.")

    pb, pp = _cmp(core, "proposal_base"), _cmp(core, "proposal_pref")
    if base != "none":
        if pb.better_job_id == c.better_job_id:
            parts.append(f"정부안이 통과되면 차이는 우대지역이 아닐 때 {label(pb.difference)}, "
                         f"우대지역으로 지정될 때 {label(pp.difference)}입니다.")
        else:
            parts.append(f"정부안이 통과되면(우대지역이 아닐 때) 결과가 바뀌어 {nm(pb.better_job_id)} 쪽이 "
                         f"{label(pb.difference)} 더 남습니다.")
    be = [x for x in (c, pb) if x.break_even]
    if be:
        x = be[0]
        line = f"{nm(x.break_even.job_id)}의 연봉이 {label(x.break_even.annual_salary, exact=True)}이면 두 공고가 같아집니다"
        line += f"({SCENARIO_NAMES[x.scenario_id]} 기준)."
        parts.append(line)
    if any(j.eligibility.status != "likely" for j in core.jobs):
        parts.append("감면 대상 여부가 확실하지 않은 공고가 있어 회사에 확인이 필요합니다.")
    return " ".join(parts)


def _facts(core: CompareCore) -> dict:
    jobs = []
    for j in core.jobs:
        jobs.append({"id": j.id, "name": core.company_names.get(j.id, j.id), "region": j.region.name,
                     "rentScope": j.rent.scope if j.rent else None, "reliefStatus": j.eligibility.status,
                     "reliefYears": {s.id: s.relief_years for s in j.scenarios}})
    return {"baseScenario": base_scenario(core), "horizonYears": core.horizon_years, "hireYear": core.hire_year,
            "betterByScenario": {c.scenario_id: c.better_job_id for c in core.comparison}, "jobs": jobs}


def explain(core: CompareCore, llm: Optional[LLMClient]) -> Explanation:
    fallback = Explanation(text=template_explanation(core), ai_generated=False, numbers_verified=True)
    if llm is None:
        return fallback
    values = build_value_list(core)
    user = ("<facts>\n" + json.dumps(_facts(core), ensure_ascii=False) + "\n</facts>\n"
            "<values>\n" + json.dumps([{"name": v["name"], "label": v["label"]} for v in values], ensure_ascii=False)
            + "\n</values>\n설명문을 써 주세요.")
    for attempt in range(2):
        try:
            out = llm.complete_json(system=SYSTEM_PROMPT, user=user, schema=SCHEMA, timeout_s=config.COMPARE_TIMEOUT_S / 2)
        except Exception:
            return fallback
        text = str((out or {}).get("text") or "").strip()
        if not text:
            continue
        ok, bad = verify_numbers(text, values)
        if ok:
            return Explanation(text=text, ai_generated=True, numbers_verified=True)
        user += f"\n\n직전 설명문에 목록에 없는 숫자가 있었습니다: {', '.join(bad)}. 목록의 label 표기만 써서 다시 써 주세요."
    return fallback
