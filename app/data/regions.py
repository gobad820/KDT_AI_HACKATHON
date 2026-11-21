"""지역 표(data/regions.csv)와 근무지 문자열 -> 시군구 코드. 규칙은 docs/data-spec.md 8, 9장.

사전으로만 찾는다. LLM 이나 추측으로 코드를 만들지 않는다.
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from typing import Dict, List, Optional

from app import config
from app.schemas import Region, RegionResolution

# 시도 약칭 -> 지역 표의 sidoName. 옛 광주광역시·전라남도는 전남광주통합특별시(2026.7.1 출범)로 본다.
SIDO_ALIASES: Dict[str, str] = {
    "서울": "서울특별시", "서울시": "서울특별시", "서울특별시": "서울특별시",
    "부산": "부산광역시", "부산시": "부산광역시", "부산광역시": "부산광역시",
    "대구": "대구광역시", "대구시": "대구광역시", "대구광역시": "대구광역시",
    "인천": "인천광역시", "인천시": "인천광역시", "인천광역시": "인천광역시",
    "대전": "대전광역시", "대전시": "대전광역시", "대전광역시": "대전광역시",
    "울산": "울산광역시", "울산시": "울산광역시", "울산광역시": "울산광역시",
    "세종": "세종특별자치시", "세종시": "세종특별자치시", "세종특별자치시": "세종특별자치시",
    "경기": "경기도", "경기도": "경기도",
    "강원": "강원특별자치도", "강원도": "강원특별자치도", "강원특별자치도": "강원특별자치도",
    "충북": "충청북도", "충청북도": "충청북도",
    "충남": "충청남도", "충청남도": "충청남도",
    "전북": "전북특별자치도", "전라북도": "전북특별자치도", "전북특별자치도": "전북특별자치도",
    "경북": "경상북도", "경상북도": "경상북도",
    "경남": "경상남도", "경상남도": "경상남도",
    "제주": "제주특별자치도", "제주도": "제주특별자치도", "제주특별자치도": "제주특별자치도",
    "광주": "전남광주통합특별시", "광주광역시": "전남광주통합특별시",
    "전남": "전남광주통합특별시", "전라남도": "전남광주통합특별시",
    "전남광주통합특별시": "전남광주통합특별시", "광주특별시": "전남광주통합특별시",
}

REMOTE_WORDS = ("재택", "원격", "리모트", "해외")


def _bool(v: str) -> bool:
    return str(v).strip().lower() in ("true", "1", "y", "yes")


@lru_cache(maxsize=1)
def _rows() -> List[dict]:
    path = config.DATA_DIR / "regions.csv"
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = []
        for r in csv.DictReader(f):
            r = {k: (v or "").strip() for k, v in r.items()}
            r["aliasList"] = [a for a in r.get("aliases", "").split("|") if a]
            r["memberList"] = [m for m in r.get("memberCodes", "").split("|") if m]
            rows.append(r)
    return rows


@lru_cache(maxsize=1)
def _by_code() -> Dict[str, dict]:
    return {r["sggCode"]: r for r in _rows()}


def reload() -> None:
    _rows.cache_clear()
    _by_code.cache_clear()


def _to_region(r: dict) -> Region:
    name = f"{r['sidoName']} {r['sggName']}".strip()
    return Region(sgg_code=r["sggCode"], name=name, region_class=r["regionClass"],
                  type_base=int(r["typeBase"]), type_pref=int(r["typePref"]),
                  pref_candidate=_bool(r["prefCandidate"]), class_uncertain=_bool(r["classUncertain"]))


def get_region(sgg_code: str) -> Optional[Region]:
    r = _by_code().get(str(sgg_code).strip())
    return _to_region(r) if r else None


def sido_code_of(sgg_code: str) -> str:
    r = _by_code().get(str(sgg_code).strip())
    return r["sidoCode"] if r and r.get("sidoCode") else str(sgg_code)[:2]


def _tokens(text: str) -> List[str]:
    text = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text)          # 괄호 안(건물명 등) 제거
    text = re.sub(r"[,/·]", " ", text)
    return [t for t in text.split() if t]


def resolve_region(location_text: str) -> RegionResolution:
    text = (location_text or "").strip()
    if not text or any(w in text for w in REMOTE_WORDS):
        return RegionResolution(candidates=[], ambiguous=True)
    tokens = _tokens(text)
    sidos = []
    for t in tokens:
        s = SIDO_ALIASES.get(t)
        if s and s not in sidos:
            sidos.append(s)

    def sgg_names(r: dict) -> List[str]:
        names = [r["sggName"]] + r["aliasList"] if r["sggName"] else r["aliasList"]
        return [n for n in names if n]

    rows = _rows()
    matched: List[dict] = []
    if sidos:
        for r in rows:
            if r["sidoName"] not in sidos:
                continue
            if not r["sggName"]:                                # 세종처럼 시군구가 없는 시도
                matched.append(r)
            elif any(n in tokens for n in sgg_names(r)):
                matched.append(r)
    else:
        for r in rows:
            if r["sggName"] and any(n in tokens for n in sgg_names(r)):
                matched.append(r)
        # 시도 없이 구 이름만 있으면 같은 이름이 다른 시도에도 있을 수 있다
        if matched and len(matched) == 1 and _name_is_shared(matched[0]["sggName"]):
            return RegionResolution(candidates=[_to_region(matched[0])], ambiguous=True)

    # 일반구가 있는 시의 시 단위 행과 구 행이 함께 걸리면 구 행만 남긴다
    member_codes = {m for r in matched for m in r["memberList"]}
    if member_codes:
        narrowed = [r for r in matched if r["sggCode"] in member_codes]
        if narrowed:
            matched = narrowed

    candidates = [_to_region(r) for r in matched]
    ambiguous = len(candidates) != 1 or len(sidos) > 1
    return RegionResolution(candidates=candidates, ambiguous=ambiguous)


SHARED_GU_NAMES = {"중구", "동구", "서구", "남구", "북구", "강서구"}


def _name_is_shared(name: str) -> bool:
    return name in SHARED_GU_NAMES
