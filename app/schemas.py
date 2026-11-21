"""API 타입. docs/api-spec.md 와 1:1로 맞춘다.

- JSON 키는 camelCase, 파이썬 속성은 snake_case 다. (예: annual_salary <-> "annualSalary")
- 모델을 만들 때는 snake_case 이름으로 넣는다. JSON 으로 내보낼 때는 dump(model) 을 쓴다.
- 금액은 원 단위 정수(int)다.
- 필드나 값 목록을 바꾸려면 docs/api-spec.md 를 먼저 고친다.
"""
from __future__ import annotations

from typing import Any, Generic, List, Literal, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")

FieldStatus = Literal["extracted", "inferred", "missing", "user"]
CompanySize = Literal["sme", "mid", "large", "public", "unknown"]
EmploymentType = Literal["regular", "contract", "intern", "daily", "unknown"]
RegionClass = Literal["capital", "metro", "other"]
Scope = Literal["sgg", "sgg_12m", "sido"]
ScenarioId = Literal["none", "current_law", "proposal_base", "proposal_pref"]
HousingMode = Literal["market_rent", "dormitory", "custom"]
InputType = Literal["number", "select", "text", "boolean"]
TraceType = Literal["extract", "question", "tool_call", "decision", "explain"]
CheckRule = Literal["age", "company_size", "industry", "employment_type", "prior_relief"]
CheckResult = Literal["pass", "fail", "unknown"]
EligibilityStatus = Literal["likely", "uncertain", "unlikely"]

SCENARIO_IDS: tuple = ("none", "current_law", "proposal_base", "proposal_pref")
SCOPES: tuple = ("sgg", "sgg_12m", "sido")
CHECK_RULES: tuple = ("age", "company_size", "industry", "employment_type", "prior_relief")
MIN_SAMPLE_COUNT = 30


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def dump(model: BaseModel) -> dict:
    """camelCase 키의 dict. API 응답, 로그, 프롬프트에 넣을 JSON 은 이 함수로 만든다."""
    return model.model_dump(by_alias=True, mode="json")


# ---- 추출 ----

class ExtractedField(ApiModel, Generic[T]):
    """api-spec 의 Field 객체."""
    value: Optional[T] = None
    status: FieldStatus
    evidence: Optional[str] = None
    note: Optional[str] = None


class Benefits(ApiModel):
    meal_allowance_monthly: ExtractedField[int]
    dormitory: ExtractedField[bool]
    housing_support_monthly: ExtractedField[int]
    others: List[str] = []


class PostingFields(ApiModel):
    company_name: ExtractedField[str]
    annual_salary: ExtractedField[int]
    work_location_text: ExtractedField[str]
    employment_type: ExtractedField[EmploymentType]
    company_size: ExtractedField[CompanySize]
    industry_text: ExtractedField[str]
    benefits: Benefits


class Region(ApiModel):
    sgg_code: str
    name: str
    region_class: RegionClass
    type_base: int
    type_pref: int
    pref_candidate: bool = False
    class_uncertain: bool = False


class RegionResolution(ApiModel):
    candidates: List[Region] = []
    ambiguous: bool = False


class Option(ApiModel):
    value: Union[str, int, bool]
    label: str


class Question(ApiModel):
    id: str
    posting_id: Optional[str] = None
    field: str
    text: str
    input_type: InputType
    options: Optional[List[Option]] = None
    required: bool = False


class TraceStep(ApiModel):
    step: int
    type: TraceType
    name: str
    summary: str


class PostingInput(ApiModel):
    id: Literal["A", "B"]
    text: str


class ExtractRequest(ApiModel):
    postings: List[PostingInput]


class ExtractedPosting(ApiModel):
    id: str
    fields: PostingFields
    region: RegionResolution


class ExtractResponse(ApiModel):
    request_id: str
    degraded: bool = False
    postings: List[ExtractedPosting]
    questions: List[Question]
    trace: List[TraceStep]


# ---- 비교 요청 ----

class Housing(ApiModel):
    mode: HousingMode = "market_rent"
    custom_monthly: Optional[int] = None


class Confirmed(ApiModel):
    company_name: str
    annual_salary: int
    sgg_code: str
    company_size: CompanySize = "unknown"
    industry_text: str = ""
    employment_type: EmploymentType = "unknown"
    non_taxable_monthly: int = 200_000
    housing: Housing = Housing()


class ComparePosting(ApiModel):
    id: Literal["A", "B"]
    confirmed: Confirmed


class Profile(ApiModel):
    """서버 코드에서만 쓴다. LLM 에 보내지 않는다."""
    age: int
    military_service_months: int = 0
    hire_year: Literal[2026, 2027] = 2027
    prior_relief: Literal["no", "yes", "unknown"] = "unknown"


class CompareOptions(ApiModel):
    horizon_years: Literal[1, 3, 5, 10] = 5
    explanation: Literal["ai", "template"] = "ai"     # template: LLM 설명문 없이 금액부터 (화면은 /api/explain으로 나중에 받음)


class CompareRequest(ApiModel):
    postings: List[ComparePosting]
    profile: Profile
    options: CompareOptions = CompareOptions()


# ---- 비교 응답 ----

class Rent(ApiModel):
    monthly_median: int
    p25: int
    p75: int
    sample_count: int
    period: str
    housing_types: List[str]
    scope: Scope
    deposit_basis: int
    conversion_rate: float
    data_as_of: str
    sufficient: bool


class Check(ApiModel):
    rule: CheckRule
    result: CheckResult
    evidence: str


class Eligibility(ApiModel):
    status: EligibilityStatus
    checks: List[Check]
    hr_question: str


class Pay(ApiModel):
    insurance: int
    final_tax: int
    local_tax: int
    net_annual: int
    net_monthly_avg: int


class PayPair(ApiModel):
    none: Pay
    with_relief: Pay


class YearRow(ApiModel):
    year: int
    relief_applied: bool
    net_annual: int
    housing_annual: int
    remaining: int
    cumulative: int


class Scenario(ApiModel):
    id: ScenarioId
    relief_years: int
    first_year_remaining: int
    cumulative_remaining: int
    relief_total: int
    yearly: List[YearRow]


class Job(ApiModel):
    id: str
    region: Region
    rent: Optional[Rent] = None          # 기숙사, 직접 입력이면 null
    housing_monthly: int = 0             # 계산에 쓴 월 주거비
    eligibility: Eligibility
    pay: PayPair
    scenarios: List[Scenario]


class BreakEven(ApiModel):
    job_id: str
    annual_salary: int


class Comparison(ApiModel):
    scenario_id: ScenarioId
    better_job_id: str
    difference: int
    break_even: Optional[BreakEven] = None


class Explanation(ApiModel):
    text: str
    ai_generated: bool
    numbers_verified: bool


class ExplainResponse(ApiModel):
    explanation: Optional[Explanation] = None
    notices: List[str] = []


class Source(ApiModel):
    name: str
    url: str
    as_of: str


class DataVersion(ApiModel):
    rent: str
    rules: str


class CompareResponse(ApiModel):
    request_id: str
    generated_at: str
    data_version: DataVersion
    degraded: bool = False
    jobs: List[Job]
    comparison: List[Comparison]
    explanation: Explanation
    trace: List[TraceStep]
    assumptions: List[str]
    notices: List[str]
    sources: List[Source]


class NeedsInputResponse(ApiModel):
    needs_input: bool = True
    questions: List[Question]
    trace: List[TraceStep]


# ---- 그 밖 ----

class ErrorBody(ApiModel):
    code: Literal["INVALID_INPUT", "POSTING_UNREADABLE", "RATE_LIMITED", "LLM_UNAVAILABLE"]
    message: str
    fallback: Literal["fix_input", "manual_input", "sample_mode"]


class ErrorResponse(ApiModel):
    error: ErrorBody


class Sample(ApiModel):
    id: str
    title: str
    postings: List[PostingInput]


class SamplesResponse(ApiModel):
    samples: List[Sample]


class HealthResponse(ApiModel):
    status: str
    data_version: DataVersion


# ---- 서버 내부에서만 쓰는 타입 (API 로 나가지 않음) ----

class CompareCore(ApiModel):
    """설명문을 쓰는 쪽(app.agent.explain)에 넘기는 계산 결과 묶음."""
    jobs: List[Job]
    comparison: List[Comparison]
    horizon_years: int
    hire_year: int
    company_names: dict = {}             # {"A": "예시소프트(가상)", "B": "보기정밀(가상)"}
    annual_salaries: dict = {}           # {"A": 38000000, "B": 34000000}


__all__: List[Any] = [n for n in dir() if not n.startswith("_")]
