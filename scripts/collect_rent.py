#!/usr/bin/env python3
"""전월세 실거래가 수집 -> SQLite (data/rent.sqlite, 테이블 rent_deals). docs/data-spec.md 2, 3장.

호출 단위는 (유형, 시군구 5자리 코드, 계약월). 이미 받은 단위는 건너뛴다(--force 로 다시 받기).
인증키: DATA_GO_KR_KEY(공통). API 마다 키가 다르면 DATA_GO_KR_KEY_OFFICETEL, _DETACHED_MULTI, _ROW_MULTI. 환경변수, 없으면 저장소 루트 .env. 키는 로그·예외·실패 파일에 남기지 않는다.
금액은 쉼표·공백을 지우고 만 원 -> 원(x10,000) 정수로 저장한다. 원본 필드는 raw_json 에 보관한다.
응답 필드명·단위는 [2차] 확인 상태다. 실제 호출 결과로 먼저 확인할 것(data-spec 2장).

예)
  python3 scripts/collect_rent.py --dry-run --codes 11680 --months 2026-05:2026-10
  python3 scripts/collect_rent.py --codes 11680,26230 --months 2026-05:2026-10
  python3 scripts/collect_rent.py --codes-from data/regions.csv --months 2025-11:2026-10
  python3 scripts/collect_rent.py --only-failed
종료 코드: 0 정상, 1 일부 실패(실패 목록 참고), 2 중단(인증·한도 오류, 설정 오류).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Optional

import httpx

from _common import (DATA_DIR, HOUSING_TYPES, get_service_key, month_range, normalize_service_key, redact,
                     shift_ym, ym_str)

DEFAULT_BASE_URL = "https://apis.data.go.kr/1613000/"

# 유형 -> (엔드포인트, 면적 필드)
TYPE_SPECS = {
    "officetel": ("RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent", "excluUseAr"),
    "detached_multi": ("RTMSDataSvcSHRent/getRTMSDataSvcSHRent", "totalFloorAr"),
    "row_multi": ("RTMSDataSvcRHRent/getRTMSDataSvcRHRent", "excluUseAr"),
}

# 이 코드가 오면 재시도해도 소용없고 계속 돌리면 호출만 낭비한다 -> 전체 중단
# 12 서비스 없음, 20 접근 거부, 22 한도 초과, 30 미등록 키, 31 기간 만료 키, 32 미등록 IP, 33 서명 오류
FATAL_REASON_CODES = {"12", "20", "22", "30", "31", "32", "33"}
NODATA_CODES = {"03"}  # NODATA_ERROR: 0건으로 본다
OK_CODES = {"000", "00"}
MAX_PAGES = 100

SCHEMA = """
CREATE TABLE IF NOT EXISTS rent_deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    housing_type TEXT NOT NULL,
    sgg_code TEXT NOT NULL,
    deal_ym TEXT NOT NULL,
    deal_year INTEGER, deal_month INTEGER, deal_day INTEGER,
    deposit_won INTEGER, monthly_rent_won INTEGER,
    area_m2 REAL, area_basis TEXT,
    contract_type TEXT,
    umd_nm TEXT,
    collected_at TEXT NOT NULL,
    raw_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rent_key ON rent_deals (housing_type, sgg_code, deal_ym);
CREATE TABLE IF NOT EXISTS collect_log (
    housing_type TEXT NOT NULL, sgg_code TEXT NOT NULL, deal_ym TEXT NOT NULL,
    item_count INTEGER NOT NULL, total_count INTEGER, collected_at TEXT NOT NULL,
    PRIMARY KEY (housing_type, sgg_code, deal_ym)
);
"""


class ApiError(Exception):
    """API 오류. fatal 이면 수집 전체를 멈춘다. 메시지에는 키가 들어가지 않게 만든다."""

    def __init__(self, message: str, code: Optional[str] = None, retryable: bool = True, fatal: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.fatal = fatal


@dataclass
class ParsedPage:
    items: list
    total_count: Optional[int]
    result_code: str = "000"


# ---------- 순수 함수: URL, 파싱, 변환 ----------

def build_url(base_url: str, housing_type: str, key: str, sgg_code: str, deal_ym: str,
              page: int = 1, rows: int = 1000) -> str:
    """완성된 요청 URL. 키는 normalize_service_key 로 한 번만 인코딩해 이어 붙인다."""
    endpoint = TYPE_SPECS[housing_type][0]
    return (f"{base_url.rstrip('/')}/{endpoint}?serviceKey={normalize_service_key(key)}"
            f"&LAWD_CD={sgg_code}&DEAL_YMD={deal_ym}&numOfRows={rows}&pageNo={page}")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _find_text(root: ET.Element, name: str) -> Optional[str]:
    for el in root.iter():
        if _local(el.tag) == name:
            return (el.text or "").strip()
    return None


def _to_int(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    t = text.replace(",", "").strip()
    return int(t) if re.fullmatch(r"-?\d+", t) else None


def parse_response(xml_text: str) -> ParsedPage:
    """응답 XML -> ParsedPage. 오류 구조와 비정상 결과 코드는 ApiError 로 올린다.

    정상: response.header.resultCode == 000, 항목은 response.body.items.item(0건이면 items 가 빔).
    오류: OpenAPI_ServiceResponse.cmmMsgHeader (returnAuthMsg/errMsg, returnReasonCode).
    """
    text = xml_text.lstrip("﻿").strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        head = " ".join(text[:120].split())
        raise ApiError(f"XML 이 아닌 응답: {head!r}", retryable=True)

    if _local(root.tag) == "OpenAPI_ServiceResponse":
        reason = _find_text(root, "returnReasonCode") or ""
        msg = _find_text(root, "returnAuthMsg") or _find_text(root, "errMsg") or "알 수 없는 오류"
        if reason in NODATA_CODES:
            return ParsedPage([], 0, reason)
        fatal = reason in FATAL_REASON_CODES or "SERVICE_KEY" in msg.upper().replace(" ", "_")
        raise ApiError(f"API 오류 {reason}: {msg}", code=reason, retryable=not fatal, fatal=fatal)

    code = _find_text(root, "resultCode")
    if code is None:
        raise ApiError(f"알 수 없는 응답 구조(루트 {_local(root.tag)})", retryable=True)
    if code in NODATA_CODES:
        return ParsedPage([], 0, code)
    if code not in OK_CODES:
        msg = _find_text(root, "resultMsg") or ""
        fatal = code in FATAL_REASON_CODES
        raise ApiError(f"API 결과 코드 {code}: {msg}", code=code, retryable=not fatal, fatal=fatal)

    items: list = []
    for el in root.iter():
        if _local(el.tag) == "items":
            for item in el:
                if _local(item.tag) == "item":
                    items.append({_local(c.tag): (c.text or "").strip() for c in item})
            break
    return ParsedPage(items, _to_int(_find_text(root, "totalCount")), code)


def parse_man_won(text: Optional[str]) -> Optional[int]:
    """'1,000' (만 원) -> 10_000_000 (원). 비었거나 숫자가 아니면 None."""
    if text is None:
        return None
    s = str(text).replace(",", "").replace(" ", "").strip()
    if not s:
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    if not d.is_finite():
        return None
    return int((d * 10000).to_integral_value())


def parse_area(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    s = str(text).replace(",", "").strip()
    if not s:
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return float(d) if d.is_finite() else None


def item_to_row(item: dict, housing_type: str, sgg_code: str, deal_ym: str, collected_at: str) -> dict:
    """원본 항목 하나를 rent_deals 한 행(dict)으로. 저장 키는 요청에 쓴 5자리 코드와 계약월이다."""
    area_field = TYPE_SPECS[housing_type][1]
    return {
        "housing_type": housing_type,
        "sgg_code": sgg_code,
        "deal_ym": deal_ym,
        "deal_year": _to_int(item.get("dealYear")),
        "deal_month": _to_int(item.get("dealMonth")),
        "deal_day": _to_int(item.get("dealDay")),
        "deposit_won": parse_man_won(item.get("deposit")),
        "monthly_rent_won": parse_man_won(item.get("monthlyRent")),
        "area_m2": parse_area(item.get(area_field)),
        "area_basis": area_field,
        "contract_type": item.get("contractType", ""),
        "umd_nm": item.get("umdNm", ""),
        "collected_at": collected_at,
        "raw_json": json.dumps(item, ensure_ascii=False, sort_keys=True),
    }


# ---------- 호출 ----------

class Fetcher:
    """(유형, 코드, 월) 한 건을 페이지 끝까지 받는다. 호출 수·재시도·대기를 관리한다."""

    def __init__(self, client: httpx.Client, key: str, base_url: str = DEFAULT_BASE_URL, rows: int = 1000,
                 retries: int = 3, retry_wait: float = 1.0, sleep: float = 0.2,
                 sleep_fn: Callable[[float], None] = time.sleep):
        self.client, self.key, self.base_url, self.rows = client, key, base_url, rows
        self.retries, self.retry_wait, self.sleep, self.sleep_fn = retries, retry_wait, sleep, sleep_fn
        self.calls = 0

    def _get_once(self, url: str) -> ParsedPage:
        self.calls += 1
        try:
            resp = self.client.get(url)
        except httpx.HTTPError as e:  # 예외 문구에 URL 이 들어갈 수 있어 가린다
            raise ApiError(redact(f"{type(e).__name__}: {e}", self.key), retryable=True) from None
        if resp.status_code != 200:
            detail = ""
            try:
                parse_response(resp.text)
            except ApiError as e:  # 본문이 오류 구조면 치명 여부를 따른다
                if e.fatal:
                    raise e from None
                detail = f": {e}"
            raise ApiError(f"HTTP {resp.status_code}{detail}", code=str(resp.status_code), retryable=True)
        return parse_response(resp.text)

    def get_page(self, htype: str, code: str, ym: str, page: int) -> ParsedPage:
        url = build_url(self.base_url, htype, self.key, code, ym, page, self.rows)
        last: Optional[ApiError] = None
        for attempt in range(1, self.retries + 1):
            if self.calls > 0 and self.sleep > 0:
                self.sleep_fn(self.sleep)
            try:
                return self._get_once(url)
            except ApiError as e:
                if e.fatal or not e.retryable:
                    raise
                last = e
                if attempt < self.retries:
                    self.sleep_fn(self.retry_wait * 2 ** (attempt - 1))
        raise ApiError(f"{self.retries}회 재시도 실패: {last}", code=last.code if last else None)

    def fetch_key(self, htype: str, code: str, ym: str) -> tuple:
        """-> (항목 목록, totalCount 또는 None). 받은 건수가 totalCount 와 다르면 ApiError."""
        items: list = []
        total: Optional[int] = None
        page = 1
        while True:
            parsed = self.get_page(htype, code, ym, page)
            if parsed.total_count is not None:
                total = parsed.total_count
            items.extend(parsed.items)
            if not parsed.items:
                break
            if total is not None and len(items) >= total:
                break
            page += 1
            if page > MAX_PAGES:
                raise ApiError(f"페이지가 {MAX_PAGES}를 넘었습니다")
        if total is not None and len(items) != total:
            raise ApiError(f"건수 불일치: totalCount {total}, 받은 {len(items)}")
        return items, total


# ---------- 저장, 실패 목록 ----------

def init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def is_done(conn: sqlite3.Connection, htype: str, code: str, ym: str) -> bool:
    return conn.execute("SELECT 1 FROM collect_log WHERE housing_type=? AND sgg_code=? AND deal_ym=?",
                        (htype, code, ym)).fetchone() is not None


def save_key(conn: sqlite3.Connection, htype: str, code: str, ym: str, items: list,
             total: Optional[int], now: Optional[str] = None) -> int:
    """한 단위를 한 트랜잭션으로 교체 저장한다(다시 받을 때 중복이 쌓이지 않는다)."""
    now = now or datetime.now().isoformat(timespec="seconds")
    rows = [item_to_row(it, htype, code, ym, now) for it in items]
    cols = list(rows[0]) if rows else []
    with conn:
        conn.execute("DELETE FROM rent_deals WHERE housing_type=? AND sgg_code=? AND deal_ym=?", (htype, code, ym))
        if rows:
            conn.executemany(f"INSERT INTO rent_deals ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                             [tuple(r[c] for c in cols) for r in rows])
        conn.execute("INSERT OR REPLACE INTO collect_log VALUES (?,?,?,?,?,?)",
                     (htype, code, ym, len(rows), total, now))
    return len(rows)


def load_failed(path: Path) -> dict:
    out: dict = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                out[(e["type"], e["code"], e["ym"])] = e
    return out


def write_failed(path: Path, failed: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e, ensure_ascii=False) for e in failed.values()]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


# ---------- 계획 ----------

def plan_keys(types: list, codes: list, months: list) -> list:
    """호출 계획. 유형 -> 코드 -> 최근 달부터 순서."""
    return [(t, c, ym) for t in types for c in codes for ym in sorted(months, reverse=True)]


def read_codes_from_csv(path: Path) -> list:
    """regions.csv 의 sggCode. memberCodes 가 있는 시 단위 행은 구 코드(실제 호출 단위)로 바꾼다."""
    if not path.is_file():
        raise ValueError(f"지역 파일이 없습니다: {path}")
    codes: list = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            members = [m for m in (row.get("memberCodes") or "").split("|") if m.strip()]
            if members:
                codes.extend(m.strip() for m in members)
            else:
                codes.append((row.get("sggCode") or "").strip())
    return validate_codes(codes)


def validate_codes(codes: list) -> list:
    out: list = []
    for c in codes:
        c = c.strip()
        if not c:
            continue
        if not re.fullmatch(r"\d{5}", c):
            raise ValueError(f"시군구 코드는 숫자 5자리여야 합니다: {c!r}")
        if c not in out:
            out.append(c)
    return out


def _types_arg(text: str) -> list:
    types = [t.strip() for t in text.split(",") if t.strip()]
    bad = [t for t in types if t not in TYPE_SPECS]
    if bad:
        raise ValueError(f"알 수 없는 유형 {bad} (가능: {', '.join(HOUSING_TYPES)})")
    return types


def default_months() -> str:
    today = datetime.now()
    y, m = today.year, today.month
    return f"{ym_str(*shift_ym(y, m, -12))}:{ym_str(*shift_ym(y, m, -1))}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="전월세 실거래가를 (유형, 시군구, 계약월) 단위로 받아 data/rent.sqlite 에 저장한다. "
                    "인증키는 환경변수 DATA_GO_KR_KEY 또는 저장소 루트 .env.",
        epilog="예: python3 scripts/collect_rent.py --dry-run --codes 11680 --months 2026-05:2026-10")
    p.add_argument("--types", default=",".join(HOUSING_TYPES), help="콤마 구분 (기본: 3종 모두)")
    p.add_argument("--months", default=None, help="계약월 범위 2025-11:2026-10, 목록 a,b, 단일 월 (기본: 직전 12개월)")
    g = p.add_argument_group("시군구 코드 (둘 중 하나)")
    g.add_argument("--codes", help="콤마 구분 5자리 코드 예: 11680,26230")
    g.add_argument("--codes-from", type=Path, help="regions.csv 경로 (시 단위 행은 memberCodes 의 구 코드를 쓴다)")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"기본 {DEFAULT_BASE_URL} (http 가 필요하면 바꿔 쓴다)")
    p.add_argument("--db", type=Path, default=DATA_DIR / "rent.sqlite")
    p.add_argument("--failed-file", type=Path, default=DATA_DIR / "raw" / "failed.jsonl")
    p.add_argument("--sleep", type=float, default=0.2, help="호출 사이 대기 초 (기본 0.2)")
    p.add_argument("--retries", type=int, default=3, help="재시도 포함 최대 시도 수 (기본 3)")
    p.add_argument("--retry-wait", type=float, default=1.0, help="재시도 대기 기본 초, 2배씩 늘린다 (기본 1.0)")
    p.add_argument("--rows", type=int, default=1000, help="numOfRows (기본 1000)")
    p.add_argument("--timeout", type=float, default=30.0, help="요청 제한 시간 초 (기본 30)")
    p.add_argument("--force", action="store_true", help="이미 받은 단위도 다시 받는다")
    p.add_argument("--only-failed", action="store_true", help="실패 목록에 있는 단위만 다시 받는다")
    p.add_argument("--dry-run", action="store_true", help="호출하지 않고 계획과 호출 수만 출력")
    return p


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


def print_plan(keys: list, args, done: set) -> None:
    todo = [k for k in keys if args.force or k not in done]
    print(f"[dry-run] 유형 {sorted({k[0] for k in keys})}, 코드 {len({k[1] for k in keys})}개, "
          f"계약월 {len({k[2] for k in keys})}개")
    print(f"[dry-run] 단위 {len(keys)}건 중 이미 받음 {len(keys) - len(todo)}건, 받을 것 {len(todo)}건")
    print(f"[dry-run] 예상 호출 수 {len(todo)} (페이지가 나뉘면 더 늘어남, 오류 시 재시도 포함 최대 {len(todo) * args.retries})")
    for t in sorted({k[0] for k in todo}):
        print(f"[dry-run]   {t}: {sum(1 for k in todo if k[0] == t)}건")
    for t, c, ym in todo[:3]:
        print("[dry-run] 예시 " + redact(build_url(args.base_url, t, "DUMMYKEY", c, ym, 1, args.rows), "DUMMYKEY"))


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        types = _types_arg(args.types)
        months = month_range(args.months or default_months())
        if args.codes and args.codes_from:
            raise ValueError("--codes 와 --codes-from 은 함께 쓸 수 없습니다")
        codes = validate_codes(args.codes.split(",")) if args.codes else (
            read_codes_from_csv(args.codes_from) if args.codes_from else [])
        if not codes and not args.only_failed:
            raise ValueError("--codes 또는 --codes-from 이 필요합니다")
    except ValueError as e:
        print(f"입력 오류: {e}", file=sys.stderr)
        return 2

    failed = load_failed(args.failed_file)
    keys = list(failed) if args.only_failed else plan_keys(types, codes, months)
    if args.only_failed and not keys:
        print("실패 목록이 비어 있습니다.")
        return 0

    done: set = set()
    if args.db.is_file():
        c = sqlite3.connect(args.db)
        try:
            done = {tuple(r) for r in c.execute("SELECT housing_type, sgg_code, deal_ym FROM collect_log")}
        except sqlite3.OperationalError:
            pass
        c.close()

    if args.dry_run:
        print_plan(keys, args, done)
        return 0

    types_needed = sorted({t for t, _, _ in keys})
    type_keys = {t: get_service_key(housing_type=t) for t in types_needed}
    missing = [t for t, k in type_keys.items() if not k]
    if missing:
        print("인증키가 없습니다. 저장소 루트 .env 에 DATA_GO_KR_KEY 를 적으세요. "
              f"API 마다 키가 다르면 DATA_GO_KR_KEY_<유형> 을 쓰세요(없는 유형: {', '.join(missing)}).", file=sys.stderr)
        return 2
    all_keys = list(dict.fromkeys(type_keys.values()))

    def hide(text: str) -> str:
        for k in all_keys:
            text = redact(text, k)
        return text

    conn = init_db(args.db)
    started = datetime.now()
    log(f"수집 시작: 단위 {len(keys)}건, DB {args.db}")
    saved = skipped = fails = total_items = 0
    exit_code = 0
    with httpx.Client(timeout=args.timeout, follow_redirects=True) as client:
        fetchers = {t: Fetcher(client, type_keys[t], args.base_url, args.rows, args.retries, args.retry_wait, args.sleep)
                    for t in types_needed}
        for i, (t, c, ym) in enumerate(keys, 1):
            if not args.force and is_done(conn, t, c, ym):
                skipped += 1
                failed.pop((t, c, ym), None)
                continue
            try:
                items, total = fetchers[t].fetch_key(t, c, ym)
                n = save_key(conn, t, c, ym, items, total)
            except ApiError as e:
                msg = hide(str(e))
                fails += 1
                failed[(t, c, ym)] = {"type": t, "code": c, "ym": ym, "error": msg,
                                      "failedAt": datetime.now().isoformat(timespec="seconds")}
                write_failed(args.failed_file, failed)
                log(f"[{i}/{len(keys)}] 실패 {t} {c} {ym}: {msg}")
                if e.fatal:
                    log("인증·한도 오류라 수집을 중단합니다. 키와 트래픽을 확인한 뒤 다시 실행하세요.")
                    exit_code = 2
                    break
                continue
            saved += 1
            total_items += n
            if (t, c, ym) in failed:
                del failed[(t, c, ym)]
                write_failed(args.failed_file, failed)
            log(f"[{i}/{len(keys)}] {t} {c} {ym}: {n}건 (totalCount {total}, 누적 호출 {sum(f.calls for f in fetchers.values())})")
    conn.close()
    write_failed(args.failed_file, failed)
    log(f"종료: 저장 {saved}단위 {total_items}건, 건너뜀 {skipped}, 실패 {fails}, 호출 {sum(f.calls for f in fetchers.values())}회, "
        f"소요 {(datetime.now() - started).seconds}초")
    if fails or failed:
        log(f"실패 목록: {args.failed_file} ({len(failed)}건). 다시 받으려면 --only-failed")
    return exit_code or (1 if fails else 0)


if __name__ == "__main__":
    sys.exit(main())
