"""중소기업 취업자 소득세 감면 대상 가능성 판정.

근거: 조세특례제한법 제30조, 시행령 제27조. 요건 요약은 docs/calc-rules.md 5장.
대상 여부를 단정하지 않는다. likely / uncertain / unlikely 와 이유, 인사팀 확인 질문을 돌려준다.
Profile(나이, 병역, 감면 이력)은 이 함수 안에서만 쓰고 근거 문장에 값을 적지 않는다.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.schemas import Check, Eligibility, Profile

from .industries import EXCLUDED, TARGET_INDUSTRIES, UNKNOWN

AGE_LIMIT_MONTHS = 35 * 12        # 만 34세 이하 = 35세 생일 전
MILITARY_CAP_MONTHS = 72          # 병역 기간은 최대 6년까지 뺀다


def _age_check(profile: Profile) -> Check:
    # 나이를 만 나이(정수)로만 받으므로 개월 단위는 범위로 본다.
    months = min(max(profile.military_service_months, 0), MILITARY_CAP_MONTHS)
    lower = profile.age * 12 - months           # 생일이 막 지난 경우
    upper = lower + 11                          # 다음 생일 직전인 경우
    if profile.age < 15 or lower >= AGE_LIMIT_MONTHS:
        return Check(rule="age", result="fail", evidence="입력한 나이에서 병역 기간을 뺀 나이가 15~34세 범위를 벗어남")
    if upper < AGE_LIMIT_MONTHS:
        return Check(rule="age", result="pass", evidence="입력한 나이에서 병역 기간을 뺀 나이가 34세 이하")
    return Check(rule="age", result="unknown", evidence="병역 기간을 뺀 나이가 34세 경계에 걸려 생일에 따라 달라짐")


def _size_check(company_size: str, evidence: Optional[str]) -> Check:
    if company_size == "sme":
        return Check(rule="company_size", result="pass", evidence=evidence or "중소기업으로 확인됨")
    if company_size in ("mid", "large", "public"):
        label = {"mid": "중견기업", "large": "대기업", "public": "공공기관"}[company_size]
        return Check(rule="company_size", result="fail", evidence=evidence or f"{label}은 감면 대상 기업이 아님")
    return Check(rule="company_size", result="unknown", evidence=evidence or "회사 규모를 알 수 없음")


def _industry_check(industry_name: str, evidence: Optional[str]) -> Check:
    if industry_name in TARGET_INDUSTRIES:
        return Check(rule="industry", result="pass", evidence=evidence or f"{industry_name}은 감면 대상 업종")
    if industry_name == EXCLUDED:
        return Check(rule="industry", result="fail", evidence=evidence or "감면 대상 업종 목록에 없음")
    return Check(rule="industry", result="unknown", evidence=evidence or "업종을 분류하지 못함")


def _employment_check(employment_type: str, evidence: Optional[str]) -> Check:
    if employment_type in ("regular", "contract", "intern"):
        return Check(rule="employment_type", result="pass", evidence=evidence or "일용근로자가 아님")
    if employment_type == "daily":
        return Check(rule="employment_type", result="fail", evidence=evidence or "일용근로자는 감면 대상에서 제외됨")
    return Check(rule="employment_type", result="unknown", evidence=evidence or "고용 형태를 알 수 없음")


def _prior_check(profile: Profile) -> Check:
    if profile.prior_relief == "no":
        return Check(rule="prior_relief", result="pass", evidence="감면 이력 없음(사용자 입력)")
    if profile.prior_relief == "yes":
        return Check(rule="prior_relief", result="unknown",
                     evidence="감면을 받은 적이 있음. 감면기간은 최초 취업일부터 이어지므로 남은 기간 확인 필요")
    return Check(rule="prior_relief", result="unknown", evidence="감면 이력을 알 수 없음")


def default_hr_question(checks: List[Check], company_name: str = "") -> str:
    """인사팀에 보낼 확인 질문 (템플릿). 금액은 넣지 않는다."""
    by_rule = {c.rule: c.result for c in checks}
    parts = []
    if by_rule.get("company_size") == "unknown":
        parts.append("귀사가 중소기업기본법상 중소기업에 해당하는지")
    if by_rule.get("industry") == "unknown":
        parts.append("주된 사업이 중소기업 취업자 소득세 감면 대상 업종인지")
    parts.append("입사 후 감면신청서를 제출하면 중소기업 취업자 소득세 감면(조세특례제한법 제30조) 처리가 가능한지")
    return ", ".join(parts) + " 확인 부탁드립니다."


def check_relief_rules(company_size: str, industry_name: str, employment_type: str, profile: Profile,
                       evidence: Optional[Dict[str, str]] = None, company_name: str = "") -> Eligibility:
    """checks 는 age, company_size, industry, employment_type, prior_relief 다섯 개를 항상 모두 돌려준다."""
    ev = evidence or {}
    checks = [
        _age_check(profile),
        _size_check(company_size, ev.get("company_size")),
        _industry_check(industry_name if industry_name else UNKNOWN, ev.get("industry")),
        _employment_check(employment_type, ev.get("employment_type")),
        _prior_check(profile),
    ]
    results = [c.result for c in checks]
    if "fail" in results:
        status = "unlikely"
    elif "unknown" in results:
        status = "uncertain"
    else:
        status = "likely"
    return Eligibility(status=status, checks=checks, hr_question=default_hr_question(checks, company_name))
