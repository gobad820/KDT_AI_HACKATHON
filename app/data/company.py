"""회사 이름으로 국민연금 가입 사업장 정보를 찾아 가입자 수를 돌려준다.

- 출처: 공공데이터포털 「국민연금공단_국민연금 가입 사업장 내역」 OpenAPI.
- 키: 환경변수 DATA_GO_KR_KEY_NPS, 없으면 DATA_GO_KR_KEY. 키가 없으면 아무것도 하지 않는다.
- 실패(시간 초과, 오류, 결과 없음, 후보가 여럿)는 모두 None. 서비스 흐름을 막지 않는다.
- 가입자 수는 회사 규모를 '추정'하는 단서로만 쓴다. 중소기업 여부는 업종별 매출 기준이라 확정하지 않는다.
- 키는 로그·예외 문구에 남기지 않는다.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import httpx

BASE = "https://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2"
TIMEOUT_S = 12.0
_CACHE: Dict[str, Optional["CompanyHit"]] = {}


@dataclass(frozen=True)
class CompanyHit:
    name: str
    headcount: int
    as_of: str          # 자료 생성 연월 (YYYYMM)
    sgg_code: str       # 법정동 시도 2자리 + 시군구 3자리


def _key() -> str:
    return (os.environ.get("DATA_GO_KR_KEY_NPS") or os.environ.get("DATA_GO_KR_KEY") or "").strip()


def enabled() -> bool:
    return bool(_key())


def normalize_name(name: str) -> str:
    n = (name or "").replace("（", "(").replace("）", ")")
    n = re.sub(r"\(\s*(주|유|사|재|합)\s*\)|㈜|주식회사|유한회사", "", n)
    return re.sub(r"[\s()\[\]]", "", n)


def _items(resp: httpx.Response) -> List[dict]:
    """JSON이든 XML이든 item 목록을 dict 목록으로 바꾼다."""
    text = resp.text.strip()
    if text.startswith("{"):
        body = resp.json().get("response", {}).get("body", {})
        items = (body.get("items") or {})
        items = items.get("item", []) if isinstance(items, dict) else items
        return items if isinstance(items, list) else [items]
    root = ET.fromstring(text)
    return [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]


def _get(client: httpx.Client, op: str, params: dict) -> List[dict]:
    try:
        r = client.get(f"{BASE}/{op}", params={"serviceKey": _key(), **params})
        if r.status_code != 200:
            return []
        return _items(r)
    except Exception:  # 예외 문구에 키가 든 URL이 들어갈 수 있어 버린다
        return []


def lookup(name: str, sgg_hint: Optional[str] = None) -> Optional[CompanyHit]:
    if not enabled() or not name or "가상" in name:
        return None
    norm = normalize_name(name)
    if len(norm) < 2:
        return None
    ck = f"{norm}|{sgg_hint or ''}"
    if ck in _CACHE:
        return _CACHE[ck]
    hit = None
    with httpx.Client(timeout=TIMEOUT_S) as client:
        rows = _get(client, "getBassInfoSearchV2", {"wkplNm": norm, "pageNo": 1, "numOfRows": 100})
        rows = [r for r in rows if normalize_name(str(r.get("wkplNm", ""))) == norm
                and str(r.get("wkplJnngStcd", "1")) == "1"]
        def sgg(r):
            return f"{r.get('ldongAddrMgplDgCd', '')}{r.get('ldongAddrMgplSgguCd', '')}"
        if sgg_hint and len(rows) > 1:
            near = [r for r in rows if sgg(r) == sgg_hint]
            rows = near or rows
        # 같은 사업장이 자료 생성 월마다 여러 행으로 나온다. 사업자번호(앞자리)가 하나면 가장 최근 행을 쓴다.
        if len({str(r.get("bzowrRgstNo", "")) for r in rows}) == 1:
            rows = sorted(rows, key=lambda r: str(r.get("dataCrtYm", "")))[-1:]
        if len(rows) == 1:
            r = rows[0]
            det = _get(client, "getDetailInfoSearchV2", {"seq": r.get("seq")})
            cnt = det[0].get("jnngpCnt") if det else None
            if cnt not in (None, ""):
                try:
                    hit = CompanyHit(name=str(r.get("wkplNm")), headcount=int(cnt),
                                     as_of=str(r.get("dataCrtYm", "")), sgg_code=sgg(r))
                except (TypeError, ValueError):
                    hit = None
    _CACHE[ck] = hit
    return hit


SME_HEADCOUNT_LIMIT = 300


def apply_company_lookup(fields: dict, regions: dict,
                         lookup_fn: Callable[[str, Optional[str]], Optional[CompanyHit]] = lookup) -> List[str]:
    """회사 규모가 비어 있는 공고만 찾아 본다. 고친 공고의 요약 문장 목록을 돌려준다(진행 기록용)."""
    targets = []
    for pid, f in fields.items():
        size = f.company_size
        if size.status == "user" or size.value not in (None, "unknown"):
            continue
        name = f.company_name.value
        if not name:
            continue
        reg = regions.get(pid)
        hint = reg.candidates[0].sgg_code if reg is not None and len(reg.candidates) == 1 else None
        targets.append((pid, name, hint))
    if not targets:
        return []
    with ThreadPoolExecutor(max_workers=2) as ex:
        hits = list(ex.map(lambda t: lookup_fn(t[1], t[2]), targets))
    notes = []
    for (pid, name, _), hit in zip(targets, hits):
        if hit is None:
            continue
        f = fields[pid]
        ym = f"{hit.as_of[:4]}-{hit.as_of[4:6]}" if len(hit.as_of) >= 6 else hit.as_of
        src = f"국민연금 가입 사업장 정보: '{hit.name}' 가입자 {hit.headcount:,}명({ym} 기준)"
        if hit.headcount < SME_HEADCOUNT_LIMIT:
            new = f.company_size.model_copy(update={
                "value": "sme", "status": "inferred", "evidence": None,
                "note": f"{src}. 300명 미만이라 중소기업으로 추정했습니다. 중소기업 여부는 업종별 매출 기준이라 회사에 확인하세요."})
        else:
            new = f.company_size.model_copy(update={
                "note": f"{src}. 300명 이상이라 중소기업이 아닐 수 있습니다."})
        fields[pid] = f.model_copy(update={"company_size": new})
        notes.append(f"{pid} 가입자 {hit.headcount:,}명")
    return notes
