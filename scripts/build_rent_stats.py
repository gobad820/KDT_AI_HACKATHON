#!/usr/bin/env python3
"""data/rent.sqlite -> data/rent_stats.json (서버가 읽는 월세 스냅샷). docs/data-spec.md 4, 5, 6장.

규칙(순서대로 첫 번째로 걸린 것만 제외 건수에 센다)
  1 월세 > 0   2 면적 33㎡ 이하(오피스텔·연립다세대 전용면적, 단독/다가구 계약면적)
  3 갱신 계약 제외(contractType 에 "갱신", 빈 값은 포함)   4 오류값(면적 0 이하·없음, 보증금 음수·없음, 계약일 없음)
  5 환산월세 = 월세 + (보증금 - 1,000만) x 전환율 / 12 (분수로 계산해 반올림), 0 이하 제외
  6 p25·중위·p75 선형 보간 후 원 단위 반올림
범위: sgg = 직전 6개월, sgg_12m = 직전 12개월, sido = 시도 6개월. --as-of 2026-11 이면 그 달은 빼고 직전 달까지.
regions.csv 에 memberCodes 가 있는 시 단위 행은 구 코드 거래를 합쳐 그 시 코드의 통계도 만든다.
금액은 원 단위 정수, 표본 0건이면 항목을 넣지 않는다.

예) python3 scripts/build_rent_stats.py --as-of 2026-11 --data-as-of 2026-11-22
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Iterable, Optional

from _common import (DATA_DIR, HOUSING_TYPES, months_before, round_half_up, to_fraction, ym_dash)

DEPOSIT_BASIS = 10_000_000
AREA_LIMIT = 33
DEFAULT_RATE = Fraction(6, 100)
DEFAULT_NOTE = ("환산월세 = 월세 + (보증금 - 1,000만 원) x 전환율 / 12. 전환율은 가정값이며 관리비는 포함하지 않는다. "
                "면적 33㎡ 이하, 갱신 계약 제외, 계약월 기준. 오피스텔·연립다세대는 전용면적, 단독/다가구는 계약면적 기준.")

# 제외 사유 이름
R_PERIOD = "기간 밖"
R_RENT = "월세 없음(전세 등)"
R_AREA = f"면적 {AREA_LIMIT}㎡ 초과"
R_RENEW = "갱신 계약"
R_ERROR = "오류값"
R_CONV = "환산월세 0 이하"
KEPT = "사용"
SCOPE_MONTHS = {"sgg": 6, "sgg_12m": 12, "sido": 6}


# ---------- 순수 함수 ----------

def converted_rent(monthly: int, deposit: int, rate=DEFAULT_RATE) -> int:
    """환산월세(원). 분수로 계산해 반올림(.5 올림). 예: 월세 50만, 보증금 500만 -> 475,000."""
    x = Fraction(monthly) + Fraction(deposit - DEPOSIT_BASIS) * to_fraction(rate) / 12
    return round_half_up(x)


def percentile(values: Iterable[int], p) -> int:
    """선형 보간(numpy 기본과 같은 방식) 백분위수, 원 단위 반올림. p 는 0~1 (0.25 등)."""
    v = sorted(values)
    if not v:
        raise ValueError("빈 목록의 백분위수는 계산할 수 없습니다")
    pos = (len(v) - 1) * to_fraction(p)
    lo = pos.__floor__()
    hi = min(lo + 1, len(v) - 1)
    return round_half_up(v[lo] + (v[hi] - v[lo]) * (pos - lo))


def keep_deal(deal: dict, area_limit: float = AREA_LIMIT) -> Optional[str]:
    """거래를 쓰면 None, 제외하면 사유(R_*). 환산월세 0 이하 판정은 build_stats 에서 한다."""
    monthly = deal.get("monthly_rent_won")
    if monthly is None or monthly <= 0:
        return R_RENT
    area = deal.get("area_m2")
    if area is not None and area > area_limit:
        return R_AREA
    if "갱신" in (deal.get("contract_type") or ""):
        return R_RENEW
    deposit, day = deal.get("deposit_won"), deal.get("deal_day")
    if area is None or area <= 0 or deposit is None or deposit < 0 or not day or day <= 0:
        return R_ERROR
    return None


def summarize(values: list, counts: Counter, period: str) -> dict:
    return {
        "period": period,
        "sampleCount": len(values),
        "p25": percentile(values, Fraction(1, 4)),
        "monthlyMedian": percentile(values, Fraction(1, 2)),
        "p75": percentile(values, Fraction(3, 4)),
        "countsByType": {t: counts[t] for t in HOUSING_TYPES if counts.get(t)},
    }


def _period(months: list) -> str:
    return f"{ym_dash(months[0])}~{ym_dash(months[-1])}"


def build_stats(deals: Iterable[dict], *, as_of: str, conversion_rate=DEFAULT_RATE, version: str,
                data_as_of: str, city_members: Optional[dict] = None, housing_types: Optional[list] = None,
                note: str = DEFAULT_NOTE, exclusions: Optional[Counter] = None) -> dict:
    """거래 dict 목록(rent_deals 컬럼 이름) -> rent_stats.json 구조.

    city_members: {시 코드: [구 코드, ...]}. 구 코드 거래를 시 코드 통계에도 합친다.
    exclusions: 넘기면 사유별 건수를 채운다(기간 밖, 규칙별 제외, 사용).
    """
    rate = to_fraction(conversion_rate)
    excl = exclusions if exclusions is not None else Counter()
    m6, m12 = months_before(as_of, 6), months_before(as_of, 12)
    in6, in12 = set(m6), set(m12)
    parents: dict = {}
    for city, members in (city_members or {}).items():
        for m in members:
            parents.setdefault(m, []).append(city)

    buckets: dict = {}  # (범위, 코드) -> (환산월세 목록, 유형 Counter)

    def add(scope: str, code: str, value: int, htype: str) -> None:
        vals, cnt = buckets.setdefault((scope, code), ([], Counter()))
        vals.append(value)
        cnt[htype] += 1

    seen_types: set = set()
    for d in deals:
        seen_types.add(d.get("housing_type"))
        ym = str(d.get("deal_ym"))
        if ym not in in12:
            excl[R_PERIOD] += 1
            continue
        reason = keep_deal(d)
        value = None
        if reason is None:
            value = converted_rent(d["monthly_rent_won"], d["deposit_won"], rate)
            if value <= 0:
                reason = R_CONV
        if reason:
            excl[reason] += 1
            continue
        excl[KEPT] += 1
        code, htype = str(d["sgg_code"]), d["housing_type"]
        for c in [code] + parents.get(code, []):
            add("sgg_12m", c, value, htype)
            if ym in in6:
                add("sgg", c, value, htype)
        if ym in in6:
            add("sido", code[:2], value, htype)

    stats: dict = {}
    sido_stats: dict = {}
    for (scope, code), (vals, cnt) in sorted(buckets.items()):
        if not vals:
            continue
        if scope == "sido":
            sido_stats[code] = summarize(vals, cnt, _period(m6))
        else:
            stats.setdefault(code, {})[scope] = summarize(vals, cnt, _period(m6 if scope == "sgg" else m12))
    stats = {c: {s: stats[c][s] for s in ("sgg", "sgg_12m") if s in stats[c]} for c in sorted(stats)}

    types = housing_types if housing_types is not None else [t for t in HOUSING_TYPES if t in seen_types]
    return {
        "version": version,
        "dataAsOf": data_as_of,
        "depositBasis": DEPOSIT_BASIS,
        "conversionRate": float(rate),
        "housingTypes": list(types),
        "note": note,
        "stats": stats,
        "sidoStats": dict(sorted(sido_stats.items())),
    }


# ---------- 입출력 ----------

def read_city_members(path: Path) -> dict:
    out: dict = {}
    if path.is_file():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                members = [m.strip() for m in (row.get("memberCodes") or "").split("|") if m.strip()]
                if members:
                    out[(row.get("sggCode") or "").strip()] = members
    return out


def read_deals(db: Path, as_of: str) -> list:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        lo, hi = months_before(as_of, 12)[0], months_before(as_of, 1)[0]
        rows = conn.execute("SELECT housing_type, sgg_code, deal_ym, deal_day, deposit_won, monthly_rent_won, "
                            "area_m2, contract_type FROM rent_deals WHERE deal_ym BETWEEN ? AND ?", (lo, hi)).fetchall()
        types = [r[0] for r in conn.execute("SELECT DISTINCT housing_type FROM rent_deals")]
    finally:
        conn.close()
    return [dict(r) for r in rows], types


def main(argv: Optional[list] = None) -> int:
    today = date.today()
    p = argparse.ArgumentParser(description="data/rent.sqlite 에서 시군구·시도별 원룸 월세 통계(rent_stats.json)를 만든다.")
    p.add_argument("--as-of", default=f"{today:%Y-%m}", help="기준월. 그 달은 빼고 직전 달까지 쓴다 (기본: 이번 달)")
    p.add_argument("--db", type=Path, default=DATA_DIR / "rent.sqlite")
    p.add_argument("--regions", type=Path, default=DATA_DIR / "regions.csv", help="시 단위 합산용 (없으면 합산 생략)")
    p.add_argument("--out", type=Path, default=DATA_DIR / "rent_stats.json")
    p.add_argument("--data-as-of", default=today.isoformat(), help="수집 기준일 YYYY-MM-DD (기본: 오늘)")
    p.add_argument("--version", default=None, help="기본: 수집 기준일")
    p.add_argument("--partial", action="store_true", help="버전 끝에 -partial 을 붙인다 (일부 지역 임시 스냅샷)")
    p.add_argument("--conversion-rate", default="0.06", help="연 전환율 (기본 0.06)")
    p.add_argument("--min-print", type=int, default=30, help="sgg 표본이 이 값 미만인 시군구를 출력 (기본 30)")
    args = p.parse_args(argv)

    if not args.db.is_file():
        print(f"수집 DB 가 없습니다: {args.db}. 먼저 scripts/collect_rent.py 를 실행하세요.", file=sys.stderr)
        return 2
    try:
        months_before(args.as_of, 1)
        rate = to_fraction(args.conversion_rate)
    except (ValueError, ZeroDivisionError) as e:
        print(f"입력 오류: {e}", file=sys.stderr)
        return 2
    version = (args.version or args.data_as_of) + ("-partial" if args.partial and not str(args.version or "").endswith("-partial") else "")

    deals, db_types = read_deals(args.db, args.as_of)
    members = read_city_members(args.regions)
    if not members:
        print(f"참고: {args.regions} 에 memberCodes 가 없어 시 단위 합산을 만들지 않습니다.")
    excl: Counter = Counter()
    doc = build_stats(deals, as_of=args.as_of, conversion_rate=rate, version=version, data_as_of=args.data_as_of,
                      city_members=members, housing_types=[t for t in HOUSING_TYPES if t in db_types], exclusions=excl)

    tmp = args.out.with_suffix(".json.tmp")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(args.out)

    print(f"기준월 {args.as_of} (직전 6개월 {_period(months_before(args.as_of, 6))}, 12개월 {_period(months_before(args.as_of, 12))}), "
          f"전환율 {float(rate)}, 유형 {doc['housingTypes']}")
    print(f"읽은 거래 {len(deals)}건 (기간 안) / 제외 사유별:")
    for reason in (R_RENT, R_AREA, R_RENEW, R_ERROR, R_CONV):
        print(f"  {reason}: {excl[reason]}")
    print(f"  사용: {excl[KEPT]}")
    thin = [c for c, v in doc["stats"].items() if v.get("sgg", {}).get("sampleCount", 0) < args.min_print]
    print(f"시군구 {len(doc['stats'])}곳, 시도 {len(doc['sidoStats'])}곳. sgg 표본 {args.min_print}건 미만 {len(thin)}곳"
          + (f": {', '.join(thin[:40])}{' ...' if len(thin) > 40 else ''}" if thin else ""))
    print(f"저장: {args.out} (version {version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
