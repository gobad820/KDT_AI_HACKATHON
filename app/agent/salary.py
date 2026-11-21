"""LLM 이 읽은 급여 표기 -> 원 단위 연봉. 환산은 코드가 한다 (docs/agent-spec.md 3장)."""
from __future__ import annotations

from typing import Optional

from app.calc.constants import MIN_WAGE_ANNUAL
from app.schemas import ExtractedField

HOURS_PER_MONTH = 209       # 주 40시간 기준 월 소정근로시간 [가정]
MAX_ANNUAL = 300_000_000


def _to_won(amount, unit: str) -> Optional[int]:
    if amount is None:
        return None
    try:
        v = float(amount)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return int(round(v * 10_000)) if unit == "만원" else int(round(v))


def normalize_salary(raw: Optional[dict]) -> ExtractedField[int]:
    """raw: {amount, unit: 만원|원, period: year|month|hour, isRange, rangeMax, negotiable, evidence}."""
    raw = raw or {}
    evidence = raw.get("evidence") or None
    if raw.get("negotiable") or raw.get("amount") in (None, "", 0):
        return ExtractedField[int](value=None, status="missing", evidence=evidence,
                                   note="연봉이 적혀 있지 않거나 협의로만 나와 있음")
    unit = raw.get("unit") if raw.get("unit") in ("만원", "원") else "만원"
    base = _to_won(raw.get("amount"), unit)
    if base is None:
        return ExtractedField[int](value=None, status="missing", evidence=evidence, note="연봉 숫자를 읽지 못함")
    period = raw.get("period") or "year"
    status, notes = "extracted", []
    if period == "month":
        value, status = base * 12, "inferred"
        notes.append("월급을 12개월로 환산함")
    elif period == "hour":
        value, status = base * HOURS_PER_MONTH * 12, "inferred"
        notes.append(f"시급을 월 {HOURS_PER_MONTH}시간, 12개월로 환산함. 근로시간 확인 필요")
    else:
        value = base
    if raw.get("isRange"):
        status = "inferred"
        notes.append("범위로 적혀 있어 하한으로 계산함")
    if value < MIN_WAGE_ANNUAL or value > MAX_ANNUAL:
        status = "inferred"
        notes.append("금액이 일반적인 범위를 벗어남. 단위를 확인해 주세요")
    return ExtractedField[int](value=value, status=status, evidence=evidence, note=" / ".join(notes) or None)


def normalize_monthly_amount(raw: Optional[dict]) -> ExtractedField[int]:
    """식대, 주거지원금처럼 월 금액. raw: {amount, unit, evidence}."""
    raw = raw or {}
    unit = raw.get("unit") if raw.get("unit") in ("만원", "원") else "원"
    v = _to_won(raw.get("amount"), unit)
    if v is None:
        return ExtractedField[int](value=None, status="missing", evidence=None, note="공고에 언급 없음")
    return ExtractedField[int](value=v, status="extracted", evidence=raw.get("evidence") or None)
