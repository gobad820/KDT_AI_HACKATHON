"""근거 대조. 추출값의 evidence 가 (개인정보를 가린) 원문에 실제로 있는지 코드로 확인한다."""
from __future__ import annotations

import re

from app.schemas import ExtractedField

WS = re.compile(r"\s+")


def norm(text: str) -> str:
    return WS.sub(" ", text or "").strip()


def evidence_in_source(evidence: str, source: str) -> bool:
    e = norm(evidence)
    return bool(e) and e in norm(source)


def verify_field(field: ExtractedField, source: str) -> ExtractedField:
    """값이 있는데 근거가 원문에 없으면 inferred 로 낮춘다."""
    if field.value is None or field.status in ("missing", "user"):
        return field
    if field.evidence and evidence_in_source(field.evidence, source):
        return field
    reason = "근거 문장이 원문에 없음" if field.evidence else "근거 문장이 없음"
    note = f"{field.note} / {reason}" if field.note else reason
    return field.model_copy(update={"status": "inferred", "note": note})


def _digit_forms(value_in_manwon: float) -> list:
    forms = set()
    if value_in_manwon == int(value_in_manwon):
        n = int(value_in_manwon)
        forms |= {str(n), f"{n:,}"}
    return list(forms)


def verify_salary(field: ExtractedField, source: str, raw_amount) -> ExtractedField:
    """환산에 쓴 숫자가 evidence 안에 있어야 한다. 없으면 missing 으로 내린다."""
    if field.value is None:
        return field
    if not (field.evidence and evidence_in_source(field.evidence, source)):
        return ExtractedField[int](value=None, status="missing", evidence=None,
                                   note="연봉 근거 문장을 원문에서 찾지 못함")
    ev = norm(field.evidence).replace(" ", "")
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        amount = None
    forms = []
    if amount is not None:
        forms = _digit_forms(amount) + ([f"{amount:g}"] if amount != int(amount) else [])
    if not ev or not any(f in ev for f in forms):
        return ExtractedField[int](value=None, status="missing", evidence=field.evidence,
                                   note="연봉 숫자를 원문 근거에서 확인하지 못함")
    return field
