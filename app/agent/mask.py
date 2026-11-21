"""LLM 에 보내기 전 개인정보 가리기. 한계: '담당자: 이름' 꼴이 아닌 이름은 못 가린다."""
from __future__ import annotations

import re

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?:\+82[-.\s]?0?|(?<!\d)0)\d{1,2}[-.\s)]?\d{3,4}[-.\s]?\d{4}(?!\d)")
CONTACT_NAME = re.compile(r"((?:담당자|채용\s*담당|인사\s*담당|문의)\s*[:：]?\s*)([가-힣]{2,4})(?=\s|$|[,(/·]|님|\s*(?:과장|대리|주임|팀장|매니저|사원))")


def mask_pii(text: str) -> str:
    text = EMAIL.sub("[이메일]", text)
    text = PHONE.sub("[전화번호]", text)
    text = CONTACT_NAME.sub(lambda m: m.group(1) + "[이름]", text)
    return text
