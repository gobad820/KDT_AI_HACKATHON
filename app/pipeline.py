"""결정적 파이프라인: 확인된 조건 -> 월세 조회 -> 감면 판정 -> 계산 -> 설명.

같은 도구를 정해진 순서로 부른다. LLM 이 없거나 실패해도 금액은 여기서 똑같이 나온다.
에이전트의 도구 호출 루프(토요일 작업)는 이 파일의 도구 함수를 그대로 쓴다.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional, Tuple, Union

from app.calc import constants as C
from app.calc.scenarios import SimJob, simulate
from app.errors import invalid_input
from app.relief.industries import UNKNOWN
from app.relief.rules import check_relief_rules
from app.schemas import (SCOPES, Check, CompareCore, CompareRequest, CompareResponse, DataVersion, Explanation,
                         Job, NeedsInputResponse, Question, Region, Rent, Source, TraceStep)

KST = timezone(timedelta(hours=9))

NOTICE_AI = "AI가 생성한 답변입니다. 금액은 서버의 계산 코드가 산출했습니다."
NOTICE_TEMPLATE = "금액은 서버의 계산 코드가 산출했습니다. 설명 문장은 정해진 틀로 작성했습니다."
NOTICE_PROPOSAL = "2026년 8월 정부 세제개편안 기준입니다. 국회에서 확정되지 않았고 지역 구분은 시행령으로 정해질 예정입니다."
NOTICE_RELIEF = "감면은 회사를 통해 신청해야 하며 대상 여부는 회사와 국세청에서 확인해야 합니다."
NOTICE_LIVING = "남는 돈에는 식비·교통비 등 생활비가 들어 있지 않습니다."

RENT_SOURCES = {
    "officetel": ("국토교통부 오피스텔 전월세 실거래가 자료", "https://www.data.go.kr/data/15126475/openapi.do"),
    "detached_multi": ("국토교통부 단독/다가구 전월세 실거래가 자료", "https://www.data.go.kr/data/15126472/openapi.do"),
    "row_multi": ("국토교통부 연립다세대 전월세 실거래가 자료", "https://www.data.go.kr"),
}
LAW_SOURCES = [
    Source(name="조세특례제한법 시행령 제27조", url="https://law.go.kr/LSW/lsLinkCommonInfo.do?lspttninfSeq=128365", as_of="2026-11-20"),
    Source(name="2026년 세제개편안(재정경제부, 2026.8.3 발표)",
           url="https://nsp.nanet.go.kr/plan/subject/detail.do?nationalPlanControlNo=PLAN0000065941", as_of="2026-11-20"),
]


@dataclass
class Deps:
    """파이프라인이 쓰는 도구. 테스트에서는 가짜를 넣는다."""
    get_region: Callable[[str], Optional[Region]]
    get_rent_stats: Callable[[str, str], Optional[Rent]]
    snapshot_info: Callable[[], dict]
    classify_industry: Callable[[str], Tuple[str, str]]          # (업종 분류 값, 근거)
    explain: Callable[[CompareCore], Explanation]
    hr_question: Optional[Callable[[List[Check], str], str]] = None
    llm_available: bool = False
    now: Callable[[], datetime] = lambda: datetime.now(KST)


def new_request_id(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(KST)
    return f"req_{now:%Y%m%d_%H%M%S}_{secrets.token_hex(2)}"


def basic_explanation(core: CompareCore) -> Explanation:
    """설명 모듈을 쓸 수 없을 때의 마지막 대체 문장."""
    first = next((c for c in core.comparison if c.scenario_id == "current_law"), core.comparison[0])
    name = core.company_names.get(first.better_job_id, f"공고 {first.better_job_id}")
    text = (f"{core.horizon_years}년 동안 세금과 주거비를 빼면 {name} 쪽이 "
            f"약 {round(first.difference / 10_000):,}만 원 더 남습니다(현행법 기준).")
    return Explanation(text=text, ai_generated=False, numbers_verified=True)


def _validate(req: CompareRequest) -> None:
    ids = sorted(p.id for p in req.postings)
    if ids != ["A", "B"]:
        raise invalid_input("공고는 A와 B 두 건이어야 합니다.")
    for p in req.postings:
        c = p.confirmed
        if c.annual_salary <= 0 or c.annual_salary > 10_000_000_000:
            raise invalid_input(f"공고 {p.id}: 연봉을 확인해 주세요.")
        if c.non_taxable_monthly < 0 or c.non_taxable_monthly * 12 >= c.annual_salary:
            raise invalid_input(f"공고 {p.id}: 비과세 금액을 확인해 주세요.")
        if c.housing.mode == "custom" and (c.housing.custom_monthly is None or c.housing.custom_monthly < 0):
            raise invalid_input(f"공고 {p.id}: 월 주거비를 입력해 주세요.")
    if req.profile.age < 0 or req.profile.age > 120 or req.profile.military_service_months < 0:
        raise invalid_input("나이와 병역 기간을 확인해 주세요.")


def _find_rent(code: str, deps: Deps) -> Tuple[Optional[Rent], List[str]]:
    """표본이 30건 이상이 될 때까지 sgg -> sgg_12m -> sido 순으로 넓힌다. (찾은 통계, 거친 범위)"""
    tried, last = [], None
    for scope in SCOPES:
        rent = deps.get_rent_stats(code, scope)
        tried.append(scope)
        if rent is not None:
            last = rent
            if rent.sufficient:
                return rent, tried
    return (None if last is None or not last.sufficient else last), tried


SCOPE_LABEL = {"sgg": "최근 6개월", "sgg_12m": "최근 12개월", "sido": "시도 전체"}


def run_compare(req: CompareRequest, deps: Deps,
                request_id: Optional[str] = None) -> Union[CompareResponse, NeedsInputResponse]:
    _validate(req)
    now = deps.now()
    request_id = request_id or new_request_id(now)
    postings = sorted(req.postings, key=lambda p: p.id)
    horizon, hire_year = req.options.horizon_years, req.profile.hire_year
    snapshot = deps.snapshot_info()
    trace: List[TraceStep] = []
    notices_extra: List[str] = []
    assumptions_housing: List[str] = []

    def add(type_: str, name: str, summary: str) -> None:
        trace.append(TraceStep(step=len(trace) + 1, type=type_, name=name, summary=summary))

    # 1) 지역과 월세
    regions, rents, housing_monthly, questions = {}, {}, {}, []
    rent_notes = []
    for p in postings:
        c = p.confirmed
        region = deps.get_region(c.sgg_code)
        if region is None:
            raise invalid_input(f"공고 {p.id}: 근무지 코드 {c.sgg_code}를 지역 표에서 찾을 수 없습니다.")
        regions[p.id] = region
        if c.housing.mode == "dormitory":
            rents[p.id], housing_monthly[p.id] = None, 0
            assumptions_housing.append(f"공고 {p.id}: 기숙사나 본가에서 다닌다고 보고 주거비를 0원으로 계산했습니다.")
        elif c.housing.mode == "custom":
            rents[p.id], housing_monthly[p.id] = None, int(c.housing.custom_monthly)
            assumptions_housing.append(f"공고 {p.id}: 입력한 월 주거비 {int(c.housing.custom_monthly):,}원으로 계산했습니다.")
        else:
            rent, tried = _find_rent(c.sgg_code, deps)
            if rent is None:
                questions.append(Question(
                    id=f"rent_{p.id}", posting_id=p.id, field="housing.customMonthly", input_type="number", required=True,
                    text=f"{c.company_name} 근무지({region.name})는 월세 표본이 부족해 통계를 낼 수 없습니다. 예상하는 월세(원)를 입력해 주세요."))
                rent_notes.append(f"{p.id} {region.name}: 시도 전체로 넓혀도 표본 부족, 확인 불가")
                continue
            rents[p.id], housing_monthly[p.id] = rent, rent.monthly_median
            note = f"{p.id} {region.name}: {SCOPE_LABEL[rent.scope]} 표본 {rent.sample_count}건"
            if len(tried) > 1:
                note += f"(표본이 30건 미만이라 {' → '.join(SCOPE_LABEL[s] for s in tried)} 순으로 넓힘)"
            rent_notes.append(note)
    if rent_notes:
        add("tool_call", "get_rent_stats", " / ".join(rent_notes))
    if questions:
        add("question", "ask_user", "월세 통계를 낼 수 없는 공고가 있어 예상 월세를 묻기로 함")
        return NeedsInputResponse(questions=questions, trace=trace)

    # 2) 감면 대상 가능성. 업종 분류(LLM)는 두 공고를 동시에 부른다
    def _classify(text: str):
        if not text.strip():
            return UNKNOWN, "업종을 분류하지 못함"
        try:
            return deps.classify_industry(text)
        except Exception:                                       # 분류 실패는 unknown 으로 둔다
            return UNKNOWN, "업종을 분류하지 못함"
    with ThreadPoolExecutor(max_workers=len(postings)) as pool:
        industries = dict(zip([p.id for p in postings], pool.map(_classify, [p.confirmed.industry_text for p in postings])))
    eligibility = {}
    for p in postings:
        c = p.confirmed
        industry_name, industry_evidence = industries[p.id]
        el = check_relief_rules(c.company_size, industry_name, c.employment_type, req.profile,
                                evidence={"industry": industry_evidence}, company_name=c.company_name)
        if deps.hr_question is not None:
            try:
                el = el.model_copy(update={"hr_question": deps.hr_question(el.checks, c.company_name)})
            except Exception:
                pass
        eligibility[p.id] = el
        if el.status == "unlikely":
            notices_extra.append(f"공고 {p.id}: 감면 대상이 아닐 가능성이 높아 감면 없음 기준으로 계산했습니다.")
        elif el.status == "uncertain":
            notices_extra.append(f"공고 {p.id}: 감면 대상 여부가 불확실합니다. 대상이 아닐 때의 값은 '감면 없음'을 보세요.")
    add("tool_call", "check_relief_rules",
        " / ".join(f"{pid}: {el.status}" for pid, el in eligibility.items()))

    # 3) 시나리오
    current_years = C.CURRENT_LAW_YEARS if hire_year <= C.CURRENT_LAW_LAST_HIRE_YEAR else 0
    add("decision", "scenario_selection",
        f"입사가 {hire_year}년이라 current_law의 감면 연수는 {current_years}. "
        "지역 구분이 미확정이라 proposal_base와 proposal_pref를 모두 계산")
    sim_jobs = [SimJob(id=p.id, annual_salary=p.confirmed.annual_salary,
                       non_taxable_monthly=p.confirmed.non_taxable_monthly, housing_monthly=housing_monthly[p.id],
                       type_base=regions[p.id].type_base, type_pref=regions[p.id].type_pref,
                       eligible=eligibility[p.id].status != "unlikely") for p in postings]
    sim = simulate(sim_jobs, hire_year, horizon)
    add("tool_call", "simulate", f"{horizon}년 기준으로 시나리오 4개의 누적 남는 돈과 손익분기 연봉을 계산")

    jobs = [Job(id=p.id, region=regions[p.id], rent=rents[p.id], housing_monthly=housing_monthly[p.id],
                eligibility=eligibility[p.id], pay=sim.pay[p.id], scenarios=sim.scenarios[p.id]) for p in postings]
    core = CompareCore(jobs=jobs, comparison=sim.comparison, horizon_years=horizon, hire_year=hire_year,
                       company_names={p.id: p.confirmed.company_name for p in postings},
                       annual_salaries={p.id: p.confirmed.annual_salary for p in postings})

    # 4) 설명. template이면 LLM을 부르지 않는다(화면이 금액을 먼저 띄우고 /api/explain으로 나중에 받음)
    if req.options.explanation == "template":
        explanation = basic_explanation(core)
    else:
        try:
            explanation = deps.explain(core)
        except Exception:
            explanation = basic_explanation(core)
    add("explain", "explanation",
        "도구 결과에 있는 숫자만 써서 설명문을 쓰고 숫자 대조를 통과" if explanation.ai_generated
        else "정해진 틀의 문장에 계산 결과를 채움")

    # 5) 고지, 가정, 출처
    for p in postings:
        region = regions[p.id]
        if region.class_uncertain:
            notices_extra.append(f"{region.name}: 정부안의 지역 유형 분류가 정해지지 않아 {region.type_base}유형으로 가정했습니다.")
        if region.pref_candidate:
            notices_extra.append(f"{region.name}: 인구감소지역이라 우대지역으로 지정될 가능성이 있으나 확정이 아닙니다.")
        if p.confirmed.annual_salary < C.MIN_WAGE_ANNUAL:
            notices_extra.append(f"공고 {p.id}: 전일제 기준 최저임금에 못 미칠 수 있습니다. 근로시간과 연봉에 포함된 항목을 확인하세요.")
    uses_rent = [r for r in rents.values() if r is not None]
    if uses_rent and snapshot.get("isSample"):
        notices_extra.append("월세는 설명용 임의 데이터입니다. 실제 실거래가가 아닙니다.")
    notices = [NOTICE_AI if explanation.ai_generated else NOTICE_TEMPLATE, NOTICE_PROPOSAL, NOTICE_RELIEF,
               NOTICE_LIVING] + notices_extra

    nontax = {p.id: p.confirmed.non_taxable_monthly for p in postings}
    if set(nontax.values()) == {C.DEFAULT_NON_TAXABLE_MONTHLY}:
        nontax_line = "비과세 식대 월 20만 원이 연봉에 들어 있다고 가정했습니다."
    else:
        nontax_line = "비과세 월액은 " + ", ".join(f"공고 {k} {v:,}원" for k, v in nontax.items()) + "으로 계산했습니다."
    assumptions = [
        "1인 가구, 부양가족 없음, 근로소득만 있는 경우로 계산했습니다.",
        nontax_line,
        "세후 금액은 연말정산 기준 연액이고 월평균은 12로 나눈 값입니다. 매달 급여명세서의 금액과 다를 수 있습니다.",
        f"2026년 4대보험 요율과 세법, 같은 연봉과 월세가 {horizon}년 동안 계속된다고 가정했습니다.",
        "1월 입사로 보고 감면기간을 연 단위로 계산했습니다.",
    ]
    if uses_rent:
        r0 = uses_rent[0]
        assumptions.append(f"월세는 보증금 {r0.deposit_basis // 10_000:,}만 원 기준으로 환산한 값입니다"
                           f"(전환율 연 {r0.conversion_rate * 100:g}% 가정).")
    assumptions += assumptions_housing
    assumptions.append("지역 유형은 공고의 근무지 기준으로 판정했습니다.")

    sources: List[Source] = []
    seen = set()
    for r in uses_rent:
        for t in r.housing_types:
            if t in RENT_SOURCES and t not in seen:
                seen.add(t)
                sources.append(Source(name=RENT_SOURCES[t][0], url=RENT_SOURCES[t][1], as_of=r.data_as_of))
    sources += LAW_SOURCES

    return CompareResponse(
        request_id=request_id, generated_at=now.isoformat(timespec="seconds"),
        data_version=DataVersion(rent=str(snapshot.get("version", "unknown")), rules=C.RULES_VERSION),
        degraded=not deps.llm_available, jobs=jobs, comparison=sim.comparison, explanation=explanation,
        trace=trace, assumptions=assumptions, notices=notices, sources=sources)
