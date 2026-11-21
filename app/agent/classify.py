"""업종 분류: 사업 내용 문장 -> 감면 대상 업종 이름 하나, excluded, unknown.

LLM 이 고르고 코드가 값 목록을 검사한다. LLM 이 없거나 실패하면 보수적인 키워드 규칙을 쓴다.
키워드 규칙은 대상 업종 이름만 고르고 excluded 는 내지 않는다(잘못 제외하면 감면을 빼먹게 되므로).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from app import config
from app.relief.industries import EXCLUDED, TARGET_INDUSTRIES, UNKNOWN

from .llm import LLMClient
from .mask import mask_pii

PROMPT_VERSION = "classify_v1"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")
ALLOWED = TARGET_INDUSTRIES + [EXCLUDED, UNKNOWN]
SCHEMA = {"type": "object", "properties": {"industryName": {"type": "string", "enum": ALLOWED},
                                           "reason": {"type": "string"}}, "required": ["industryName", "reason"]}

# (키워드, 업종). 앞에서부터 본다. 애매한 단어가 섞이면 unknown.
KEYWORDS = [
    (("제조", "생산공장", "가공 공장"), "제조업"),
    (("소프트웨어", "SW 개발", "앱 개발", "플랫폼 개발", "클라우드", "IT 서비스", "정보통신", "게임 개발", "웹 서비스"), "정보통신업"),
    (("건설", "시공"), "건설업"),
    (("도매", "소매", "유통"), "도매 및 소매업"),
    (("물류", "운송", "창고"), "운수 및 창고업"),
    (("연구개발",), "연구개발업"),
]
UNSURE_WORDS = ("금융", "보험", "증권", "은행", "병원", "의원", "의료", "약국", "법무", "법률", "회계", "세무",
                "주점", "카페", "음료", "임대", "가상자산", "코인", "통관", "수의", "공공기관", "공사", "공단")


def keyword_classify(text: str) -> Tuple[str, str]:
    t = text or ""
    if any(w in t for w in UNSURE_WORDS):
        return UNKNOWN, "대상 업종인지 공고만으로 판단하기 어려움"
    hits = {name for words, name in KEYWORDS if any(w in t for w in words)}
    if len(hits) == 1:
        name = hits.pop()
        return name, f"사업 내용 '{t[:40]}'을 {name}으로 분류(키워드 규칙)"
    return UNKNOWN, "업종을 분류하지 못함" if not hits else "여러 업종에 걸쳐 있어 주된 사업을 알 수 없음"


def classify_industry(industry_text: str, llm: Optional[LLMClient]) -> Tuple[str, str]:
    text = (industry_text or "").strip()
    if not text:
        return UNKNOWN, "사업 내용이 없음"
    if llm is None:
        return keyword_classify(text)
    try:
        out = llm.complete_json(system=SYSTEM_PROMPT + "\n\n대상 업종 목록: " + ", ".join(TARGET_INDUSTRIES),
                                user=f"<industry>{mask_pii(text)[:500]}</industry>", schema=SCHEMA,
                                timeout_s=config.EXTRACT_TIMEOUT_S)
    except Exception:
        return keyword_classify(text)
    name = (out or {}).get("industryName")
    reason = str((out or {}).get("reason") or "")[:120]
    if name not in ALLOWED:
        return UNKNOWN, "분류 결과가 업종 목록에 없음"
    return name, reason or f"사업 내용을 {name}으로 분류"
