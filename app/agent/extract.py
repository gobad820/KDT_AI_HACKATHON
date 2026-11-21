"""EXTRACT: 공고 원문 -> PostingFields.

흐름: mask_pii -> LLM(JSON) -> 단위 환산(코드) -> 근거 대조(코드).
LLM 은 금액을 원 단위로 바꾸지 않는다. 공고 원문은 구분 태그 안에 넣어 데이터로 다룬다.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

from app import config
from app.schemas import Benefits, ExtractedField, PostingFields, PostingInput

from .evidence import verify_field, verify_salary
from .llm import LLMClient, LLMUnavailable
from .mask import mask_pii
from .salary import normalize_monthly_amount, normalize_salary

PROMPT_VERSION = "extract_v1"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")


class PostingUnreadable(ValueError):
    """연봉과 근무지를 둘 다 읽지 못한 공고."""


def _text_item(extra: Optional[dict] = None) -> dict:
    props = {"value": {"type": ["string", "null"]}, "evidence": {"type": ["string", "null"]}}
    props.update(extra or {})
    return {"type": "object", "properties": props, "required": list(props)}


def _money_item() -> dict:
    return {"type": "object", "properties": {
        "amount": {"type": ["number", "null"]}, "unit": {"type": ["string", "null"], "enum": ["만원", "원", None]},
        "evidence": {"type": ["string", "null"]}}, "required": ["amount", "unit", "evidence"]}


EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "companyName": _text_item(),
        "salary": {"type": "object", "properties": {
            "amount": {"type": ["number", "null"]},
            "unit": {"type": ["string", "null"], "enum": ["만원", "원", None]},
            "period": {"type": ["string", "null"], "enum": ["year", "month", "hour", None]},
            "isRange": {"type": "boolean"}, "rangeMax": {"type": ["number", "null"]},
            "negotiable": {"type": "boolean"}, "evidence": {"type": ["string", "null"]}},
            "required": ["amount", "unit", "period", "isRange", "rangeMax", "negotiable", "evidence"]},
        "workLocationText": _text_item({"multipleLocations": {"type": "boolean"}}),
        "employmentType": {"type": "object", "properties": {
            "value": {"type": "string", "enum": ["regular", "contract", "intern", "daily", "unknown"]},
            "evidence": {"type": ["string", "null"]}}, "required": ["value", "evidence"]},
        "companySize": {"type": "object", "properties": {
            "value": {"type": "string", "enum": ["sme", "mid", "large", "public", "unknown"]},
            "explicit": {"type": "boolean"}, "evidence": {"type": ["string", "null"]}},
            "required": ["value", "explicit", "evidence"]},
        "industryText": _text_item(),
        "mealAllowanceMonthly": _money_item(),
        "dormitory": {"type": "object", "properties": {"value": {"type": ["boolean", "null"]},
                                                      "evidence": {"type": ["string", "null"]}},
                      "required": ["value", "evidence"]},
        "housingSupportMonthly": _money_item(),
        "others": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["companyName", "salary", "workLocationText", "employmentType", "companySize", "industryText",
                 "mealAllowanceMonthly", "dormitory", "housingSupportMonthly", "others"],
}


def _field(value, evidence, missing_note: str = "공고에 언급 없음", note: Optional[str] = None) -> ExtractedField:
    if value in (None, ""):
        return ExtractedField(value=None, status="missing", evidence=None, note=missing_note)
    return ExtractedField(value=value, status="extracted", evidence=evidence or None, note=note)


def to_fields(raw: dict, masked_text: str) -> PostingFields:
    """LLM 출력(dict) -> PostingFields. 환산과 근거 대조는 여기서 코드로 한다."""
    g = lambda k: raw.get(k) or {}

    salary_raw = g("salary")
    salary = verify_salary(normalize_salary(salary_raw), masked_text, salary_raw.get("amount"))

    loc = g("workLocationText")
    location = verify_field(_field(loc.get("value"), loc.get("evidence")), masked_text)
    if location.value and loc.get("multipleLocations"):
        location = location.model_copy(update={"status": "inferred", "note": "근무지가 여러 곳으로 적혀 있음"})

    emp = g("employmentType")
    emp_value = emp.get("value") if emp.get("value") in ("regular", "contract", "intern", "daily") else None
    employment = verify_field(_field(emp_value, emp.get("evidence"), "고용 형태가 적혀 있지 않음"), masked_text)
    if employment.value is None:
        employment = employment.model_copy(update={"value": "unknown"})

    size = g("companySize")
    size_value = size.get("value") if size.get("value") in ("sme", "mid", "large", "public") else None
    if size_value is None:
        company_size = ExtractedField(value="unknown", status="missing", evidence=None,
                                      note="공고에 회사 규모가 적혀 있지 않음")
    else:
        company_size = verify_field(_field(size_value, size.get("evidence")), masked_text)
        if not size.get("explicit") and company_size.status == "extracted":
            company_size = company_size.model_copy(update={"status": "inferred", "note": "규모가 직접 적혀 있지 않고 단서만 있음"})

    name = g("companyName")
    industry = g("industryText")
    dorm = g("dormitory")
    dormitory = verify_field(_field(dorm.get("value") if dorm.get("value") is True else None, dorm.get("evidence")),
                             masked_text)
    meal = normalize_monthly_amount(g("mealAllowanceMonthly"))
    housing = normalize_monthly_amount(g("housingSupportMonthly"))
    others = [str(x)[:100] for x in (raw.get("others") or []) if str(x).strip()][:20]

    return PostingFields(
        company_name=verify_field(_field(name.get("value"), name.get("evidence"), "회사명이 적혀 있지 않음"), masked_text),
        annual_salary=salary,
        work_location_text=location,
        employment_type=employment,
        company_size=company_size,
        industry_text=verify_field(_field(industry.get("value"), industry.get("evidence"), "사업 내용이 적혀 있지 않음"),
                                   masked_text),
        benefits=Benefits(meal_allowance_monthly=verify_field(meal, masked_text), dormitory=dormitory,
                          housing_support_monthly=verify_field(housing, masked_text), others=others),
    )


def _extract_one(posting: PostingInput, llm: LLMClient) -> PostingFields:
    masked = mask_pii(posting.text)
    user = f"아래 공고에서 조건을 읽어 주세요.\n<posting>\n{masked}\n</posting>"
    try:
        raw = llm.complete_json(system=SYSTEM_PROMPT, user=user, schema=EXTRACT_SCHEMA,
                                timeout_s=config.EXTRACT_TIMEOUT_S)
    except LLMUnavailable:
        raise
    except Exception as exc:                                   # 어댑터의 예상 못 한 오류도 대체 흐름으로
        raise LLMUnavailable(f"추출 실패: {type(exc).__name__}") from None
    if not isinstance(raw, dict):
        raise LLMUnavailable("추출 결과 형식 오류")
    fields = to_fields(raw, masked)
    if fields.annual_salary.value is None and fields.work_location_text.value is None:
        raise PostingUnreadable(f"공고 {posting.id}에서 연봉과 근무지를 읽지 못했습니다. 채용공고 본문이 맞는지 확인해 주세요.")
    return fields


def extract_postings(postings: List[PostingInput], llm: Optional[LLMClient]) -> Dict[str, PostingFields]:
    if llm is None:
        raise LLMUnavailable("LLM 이 설정되지 않음")
    with ThreadPoolExecutor(max_workers=max(1, len(postings))) as pool:
        futures = {p.id: pool.submit(_extract_one, p, llm) for p in postings}
        return {pid: f.result() for pid, f in futures.items()}
