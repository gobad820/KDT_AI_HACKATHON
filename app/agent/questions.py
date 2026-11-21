"""되묻기 질문 (docs/agent-spec.md 5장). 공고별 질문은 최대 5개, profile 질문 4개는 고정 문구로 마지막에 붙인다."""
from __future__ import annotations

from typing import Dict, List

from app.schemas import Option, PostingFields, Question, RegionResolution

MAX_POSTING_QUESTIONS = 5

SIZE_OPTIONS = [Option(value="sme", label="중소기업"), Option(value="mid", label="중견기업"),
                Option(value="large", label="대기업"), Option(value="public", label="공공기관"),
                Option(value="unknown", label="모름")]

PROFILE_QUESTIONS = [
    dict(field="profile.age", text="근로계약을 맺는 시점의 만 나이를 알려주세요.", input_type="number", required=True),
    dict(field="profile.militaryServiceMonths", text="병역을 마쳤다면 복무 기간을 개월 수로 적어 주세요. 해당이 없으면 0입니다.",
         input_type="number", required=False),
    dict(field="profile.hireYear", text="입사 예정 시기를 골라 주세요.", input_type="select", required=True,
         options=[Option(value=2026, label="2026년 안"), Option(value=2027, label="2027년 이후")]),
    dict(field="profile.priorRelief", text="중소기업 취업자 소득세 감면을 받은 적이 있나요?", input_type="select", required=False,
         options=[Option(value="no", label="없음"), Option(value="yes", label="있음"), Option(value="unknown", label="모름")]),
]


def _who(pid: str, f: PostingFields) -> str:
    return f"{f.company_name.value} 공고" if f.company_name.value else f"공고 {pid}"


def _posting_questions(pid: str, f: PostingFields, region: RegionResolution) -> List[dict]:
    who, qs = _who(pid, f), []
    sal = f.annual_salary
    if sal.value is None:
        quoted = f"'{sal.evidence}'" if sal.evidence else "적혀 있지 않거나 협의"
        qs.append(dict(field="annualSalary", input_type="number", required=True,
                       text=f"{who}에는 연봉이 {quoted}로만 나와 있습니다. 제안받았거나 예상하는 연봉(원)을 입력해 주세요."))
    elif sal.status == "inferred":
        qs.append(dict(field="annualSalary", input_type="number", required=True,
                       text=f"{who}의 연봉을 {sal.value:,}원으로 계산했습니다({sal.note}). 이 금액으로 비교할까요? 다르면 고쳐 주세요."))
    if not f.work_location_text.value:
        qs.append(dict(field="workLocationText", input_type="text", required=True,
                       text=f"{who}에 근무지가 적혀 있지 않습니다. 근무할 시군구를 알려 주세요."))
    elif len(region.candidates) > 1:
        qs.append(dict(field="sggCode", input_type="select", required=True,
                       options=[Option(value=c.sgg_code, label=c.name) for c in region.candidates],
                       text=f"{who}의 근무지 '{f.work_location_text.value}'가 여러 지역에 해당할 수 있습니다. 어디인가요?"))
    elif not region.candidates or region.ambiguous:
        qs.append(dict(field="workLocationText", input_type="text", required=True,
                       text=f"{who}의 근무지 '{f.work_location_text.value}'를 지역 표에서 찾지 못했습니다. 시군구까지 적어 주세요."))
    if f.company_size.value == "unknown" or f.company_size.status == "inferred":
        qs.append(dict(field="companySize", input_type="select", required=True, options=SIZE_OPTIONS,
                       text=f"{who}에는 회사 규모가 적혀 있지 않습니다. 어디에 해당하나요?" if f.company_size.value == "unknown"
                       else f"{who}의 회사 규모를 단서로만 '{f.company_size.value}'로 읽었습니다. 맞나요?"))
    if f.benefits.dormitory.value is True:
        qs.append(dict(field="housing.mode", input_type="boolean", required=False,
                       text=f"{who}에 기숙사가 제공된다고 나와 있습니다. 이용할 계획인가요?"))
    if f.employment_type.value in ("intern", "contract"):
        kind = "인턴" if f.employment_type.value == "intern" else "계약직"
        qs.append(dict(field="proceed", input_type="boolean", required=False,
                       text=f"{who}는 {kind} 채용이라 여러 해 누적 비교가 맞지 않을 수 있습니다. 그래도 같은 조건이 이어진다고 보고 비교할까요?"))
    return qs


def build_questions(fields: Dict[str, PostingFields], regions: Dict[str, RegionResolution]) -> List[Question]:
    pending = []
    for pid in sorted(fields):
        for q in _posting_questions(pid, fields[pid], regions.get(pid, RegionResolution())):
            pending.append((pid, q))
    pending.sort(key=lambda x: not x[1]["required"])           # 필수 먼저 (안정 정렬)
    out: List[Question] = []
    for pid, q in pending[:MAX_POSTING_QUESTIONS]:
        out.append(Question(id=f"q{len(out) + 1}", posting_id=pid, **q))
    for q in PROFILE_QUESTIONS:
        out.append(Question(id=f"q{len(out) + 1}", posting_id=None, **q))
    return out
