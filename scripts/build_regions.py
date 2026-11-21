#!/usr/bin/env python3
"""법정동 코드 파일 + 인구감소지역 목록 -> data/regions.csv (지역 유형 테이블). docs/data-spec.md 7, 8장.

가정한 입력 형식 (실제 파일로는 검증하지 못했다. 형식이 다르면 분명한 메시지를 내고 멈춘다)
  1) 법정동 코드 파일: 행정표준코드관리시스템(code.go.kr) 내려받기 텍스트. 탭 구분, 첫 줄이 헤더,
     컬럼 `법정동코드`(10자리), `법정동명`("경기도 수원시 장안구"처럼 시도부터 공백 구분), `폐지여부`
     ("폐지"/"Y"/"1"/"true" 는 폐지, 그 밖(예: "존재")은 현재 사용). 인코딩 cp949 또는 utf-8(BOM 가능) 자동 시도.
  2) 인구감소지역 목록: CSV(utf-8 또는 cp949). 컬럼 `sggCode`(5자리) 가 있거나, `시도`와 `시군구` 두 컬럼
     (시도는 "부산"/"부산광역시"/"전남" 등 약칭 가능). 둘 다 있으면 둘 다 쓴다. 생략하면 prefCandidate 가 모두 false.
출력 `data/regions.csv` (UTF-8, BOM 없음): sggCode,sidoCode,sidoName,sggName,aliases,memberCodes,regionClass,
  typeBase,typePref,prefCandidate,classUncertain,note   (aliases, memberCodes 는 `|` 구분, 불리언은 true/false)

규칙
  - 10자리 코드 중 앞 5자리가 시군구, 뒤 5자리가 00000, 시도 행(앞 2자리 뒤가 모두 0)이 아닌 행만, 폐지 제외.
    이름이 시도 이름뿐인 행(세종 36110)은 sggName 을 비운다.
  - 분류(typeBase, typePref): capital 11·28·41 -> 1,2 / metro 26·27·30·31 -> 2,3 / 세종 36 -> metro 2,3 미확정 /
    그 밖 -> other 3,4. 광주 29 는 (통합 전 파일이면) metro 2,3 으로 둔다.
    전남광주통합특별시는 시도 코드를 파일에서 확인해 --merged-sido-code 로, 옛 광주 5개 구의 새 코드를
    --old-gwangju-codes 로 받는다. 옛 광주 구 -> metro 2,3 미확정, 나머지(옛 전남) -> other 3,4.
  - "OO시 OO구" 꼴의 일반구는 시 단위 행을 따로 만들고 memberCodes 에 구 코드를 넣는다(시 코드가 파일에 없으면
    구 코드 앞 4자리 + 0 으로 추정하고 note 에 적는다). 구 행도 그대로 둔다.
예) python3 scripts/build_regions.py --law-code-file data/raw/법정동코드.txt --depop-file data/raw/depop.csv \\
      --merged-sido-code 29 --old-gwangju-codes 29110,29140,29155,29170,29200
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Iterable, Optional

from _common import DATA_DIR

COLUMNS = ["sggCode", "sidoCode", "sidoName", "sggName", "aliases", "memberCodes", "regionClass",
           "typeBase", "typePref", "prefCandidate", "classUncertain", "note"]
CAPITAL, METRO = {"11", "28", "41"}, {"26", "27", "29", "30", "31"}
SEJONG = "36"
ABOLISHED = {"폐지", "y", "1", "true"}
GU_PATTERN = re.compile(r"^(?P<city>\S+시) (?P<gu>\S+구)$")
DEPOP_NOTE = "인구감소지역 후보. 고시 목록으로 확인"


class FormatError(ValueError):
    """입력 파일 형식이 가정과 다를 때."""


# ---------- 읽기 ----------

def read_text_any(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise FormatError(f"{path}: utf-8, cp949 어느 쪽으로도 읽을 수 없습니다")


def parse_law_rows(text: str) -> list:
    """탭 구분 텍스트 -> [{code, name, abolished}]. 헤더에 필요한 컬럼이 없으면 FormatError."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise FormatError("법정동 코드 파일이 비어 있습니다")
    header = [h.strip() for h in lines[0].split("\t")]
    need = ["법정동코드", "법정동명", "폐지여부"]
    missing = [c for c in need if c not in header]
    if missing:
        raise FormatError(f"법정동 코드 파일 헤더에 {missing} 컬럼이 없습니다. 탭 구분이어야 하고 첫 줄이 "
                          f"{need} 여야 합니다. 읽은 헤더: {header}")
    ci, ni, ai = (header.index(c) for c in need)
    rows = []
    for ln in lines[1:]:
        cells = [c.strip() for c in ln.split("\t")]
        if len(cells) <= max(ci, ni, ai):
            continue
        if re.fullmatch(r"\d{10}", cells[ci]):
            rows.append({"code": cells[ci], "name": cells[ni], "abolished": cells[ai].lower() in ABOLISHED})
    if not rows:
        raise FormatError("10자리 법정동코드 행을 하나도 찾지 못했습니다. 파일 형식을 확인하세요")
    return rows


def parse_depop(text: str) -> list:
    """인구감소지역 CSV -> [{code, sido, name}] (없는 값은 빈 문자열)."""
    reader = csv.DictReader(text.splitlines())
    headers = [(h or "").strip() for h in (reader.fieldnames or [])]
    has_code, has_name = "sggCode" in headers, "시도" in headers and "시군구" in headers
    if not (has_code or has_name):
        raise FormatError(f"인구감소지역 CSV 에 `sggCode` 또는 `시도`+`시군구` 컬럼이 필요합니다. 읽은 헤더: {headers}")
    out = []
    for row in reader:
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        code = row.get("sggCode", "")
        if code and not re.fullmatch(r"\d{5}", code):
            raise FormatError(f"인구감소지역 sggCode 는 숫자 5자리여야 합니다: {code!r}")
        if code or (has_name and row.get("시군구")):
            out.append({"code": code, "sido": row.get("시도", ""), "name": row.get("시군구", "")})
    return out


# ---------- 순수 규칙 ----------

def classify(sido_code: str, sgg_code: str, merged_sido_code: Optional[str] = None,
             old_gwangju_codes: Iterable[str] = ()) -> dict:
    """시도·시군구 코드 -> regionClass, typeBase, typePref, classUncertain, note."""
    if merged_sido_code and sido_code == merged_sido_code:
        if sgg_code in set(old_gwangju_codes):
            return dict(regionClass="metro", typeBase=2, typePref=3, classUncertain=True,
                        note="분류 미확정. 옛 광주광역시 구")
        return dict(regionClass="other", typeBase=3, typePref=4, classUncertain=False,
                    note="옛 전라남도 시군 [가정]")
    if sido_code in CAPITAL:
        return dict(regionClass="capital", typeBase=1, typePref=2, classUncertain=False, note="")
    if sido_code == SEJONG:
        return dict(regionClass="metro", typeBase=2, typePref=3, classUncertain=True, note="분류 미확정")
    if sido_code in METRO:
        return dict(regionClass="metro", typeBase=2, typePref=3, classUncertain=False, note="")
    return dict(regionClass="other", typeBase=3, typePref=4, classUncertain=False, note="")


_SIDO_KEYS = [("전남광주", "전남광주"), ("서울", "서울"), ("부산", "부산"), ("대구", "대구"), ("인천", "인천"),
              ("광주", "광주"), ("대전", "대전"), ("울산", "울산"), ("세종", "세종"), ("경기", "경기"),
              ("강원", "강원"), ("충청북", "충북"), ("충북", "충북"), ("충청남", "충남"), ("충남", "충남"),
              ("전라북", "전북"), ("전북", "전북"), ("전라남", "전남"), ("전남", "전남"), ("경상북", "경북"),
              ("경북", "경북"), ("경상남", "경남"), ("경남", "경남"), ("제주", "제주")]


def sido_key(name: str) -> str:
    """'부산광역시'/'부산' -> '부산', '전라남도'/'전남' -> '전남'. 모르는 이름은 공백 제거한 원문."""
    n = name.replace(" ", "")
    for prefix, key in _SIDO_KEYS:
        if n.startswith(prefix):
            return key
    return n


def make_aliases(sido_name: str, sgg_name: str, old_prefix: str = "") -> list:
    """약칭과 옛 이름. 세종처럼 시군구 이름이 없으면 시도 약칭을 쓴다."""
    out: list = []
    if not sgg_name:
        base = re.sub(r"(특별자치시|특별시|광역시|특별자치도|도)$", "", sido_name)
        out += [base + "시", base] if sido_name.endswith("시") else [base]
    else:
        last = sgg_name.split(" ")[-1]
        for n in {sgg_name, last}:
            short = re.sub(r"[시군구]$", "", n)
            if len(short) >= 2 and short != n:
                out.append(short)
        if old_prefix:
            out.append(f"{old_prefix} {sgg_name}")
    return list(dict.fromkeys(a for a in out if a and a != sgg_name))


def _name_of(sido_name: str, full_name: str) -> str:
    rest = full_name[len(sido_name):].strip() if full_name.startswith(sido_name) else " ".join(full_name.split()[1:])
    return rest


def build_region_rows(law_rows: list, depop: Optional[list] = None, merged_sido_code: Optional[str] = None,
                      old_gwangju_codes: Iterable[str] = (), warn=lambda msg: None) -> list:
    """법정동 행 + 인구감소지역 -> regions 행(dict) 목록(sggCode 순). 옵션 검증 포함."""
    old = list(dict.fromkeys(old_gwangju_codes))
    alive = [r for r in law_rows if not r["abolished"]]
    sido_names = {r["code"][:2]: r["name"] for r in alive if r["code"][2:] == "00000000"}

    merged_sidos = {c: n for c, n in sido_names.items() if "전남광주" in n}
    if merged_sidos and not merged_sido_code:
        raise FormatError(f"파일에 전남광주통합특별시 시도 행이 있습니다 {merged_sidos}. "
                          f"--merged-sido-code 와 --old-gwangju-codes 를 지정하세요")
    if merged_sido_code:
        if merged_sido_code not in sido_names:
            raise FormatError(f"--merged-sido-code {merged_sido_code} 가 파일의 현재 시도 코드에 없습니다. "
                              f"파일의 시도 코드: {sorted(sido_names.items())}")
        if not old:
            raise FormatError("--merged-sido-code 를 쓰면 --old-gwangju-codes(옛 광주 5개 구의 새 코드)도 필요합니다")
        have = {r["code"][:5] for r in alive}
        bad = [c for c in old if c not in have or not c.startswith(merged_sido_code)]
        if bad:
            raise FormatError(f"--old-gwangju-codes {bad} 가 파일에 없거나 시도 코드 {merged_sido_code} 로 시작하지 않습니다")
        if len(old) != 5:
            warn(f"옛 광주 구 코드가 {len(old)}개입니다(5개를 기대). 확인하세요")

    rows: dict = {}
    for r in alive:
        c = r["code"]
        if c[5:] != "00000" or c[2:5] == "000":
            continue
        sgg, sido = c[:5], c[:2]
        sido_name = sido_names.get(sido) or r["name"].split()[0]
        name = _name_of(sido_name, r["name"])
        if sgg in rows:
            continue
        is_old_gj = bool(merged_sido_code) and sido == merged_sido_code and sgg in old
        is_old_jn = bool(merged_sido_code) and sido == merged_sido_code and sgg not in old
        old_prefix = "광주광역시" if is_old_gj else ("전라남도" if is_old_jn and name else "")
        rows[sgg] = {"sggCode": sgg, "sidoCode": sido, "sidoName": sido_name, "sggName": name,
                     "aliases": make_aliases(sido_name, name, old_prefix), "memberCodes": [],
                     "prefCandidate": False, **classify(sido, sgg, merged_sido_code, old)}
    if not rows:
        raise FormatError("시군구 단위 행(뒤 5자리 00000)을 하나도 찾지 못했습니다. 파일 형식을 확인하세요")

    # 일반구가 있는 시: 시 단위 행 + memberCodes
    groups: dict = {}
    for r in list(rows.values()):
        m = GU_PATTERN.match(r["sggName"])
        if m:
            groups.setdefault((r["sidoCode"], m.group("city")), []).append(r["sggCode"])
    for (sido, city), members in groups.items():
        members.sort()
        existing = next((r for r in rows.values() if r["sidoCode"] == sido and r["sggName"] == city), None)
        if existing is None:
            code = members[0][:4] + "0"
            guess = code in rows
            if guess:  # 추정 코드가 다른 시군구와 겹치면 만들지 않는다
                warn(f"{city}: 시 단위 코드가 파일에 없고 추정 코드 {code} 가 이미 있어 시 행을 만들지 않았습니다")
                continue
            first = rows[members[0]]
            existing = {"sggCode": code, "sidoCode": sido, "sidoName": first["sidoName"], "sggName": city,
                        "aliases": make_aliases(first["sidoName"], city), "memberCodes": [], "prefCandidate": False,
                        **classify(sido, code, merged_sido_code, old)}
            existing["note"] = (existing["note"] + "; " if existing["note"] else "") + "시 단위 코드가 파일에 없어 추정(구 코드 앞 4자리+0)"
            rows[code] = existing
        existing["memberCodes"] = members
        existing["note"] = (existing["note"] + "; " if existing["note"] else "") + "일반구 합산 행(memberCodes)"

    # 인구감소지역
    unmatched: list = []
    for i, d in enumerate(depop or []):
        hit = False
        for r in rows.values():
            if d["code"] and r["sggCode"] == d["code"]:
                hit = True
            elif d["name"] and not d["code"]:
                keys = {sido_key(r["sidoName"])}
                if merged_sido_code and r["sidoCode"] == merged_sido_code:
                    keys = {"광주"} if r["sggCode"] in old else {"전남"}
                if sido_key(d["sido"]) in keys and d["name"].replace(" ", "") == r["sggName"].replace(" ", ""):
                    hit = True
            if hit:
                r["prefCandidate"] = True
                r["note"] = (r["note"] + "; " if r["note"] else "") + DEPOP_NOTE
                break
        if not hit:
            unmatched.append(d["code"] or f"{d['sido']} {d['name']}")
    if depop:
        warn(f"인구감소지역 {len(depop)}곳 중 {len(depop) - len(unmatched)}곳 매칭"
             + (f", 미매칭 {len(unmatched)}곳: {', '.join(unmatched)} (개편·코드 변경 여부 확인)" if unmatched else ""))
    return [rows[k] for k in sorted(rows)]


def to_csv_row(r: dict) -> dict:
    out = dict(r)
    out["aliases"] = "|".join(r["aliases"])
    out["memberCodes"] = "|".join(r["memberCodes"])
    out["prefCandidate"] = "true" if r["prefCandidate"] else "false"
    out["classUncertain"] = "true" if r["classUncertain"] else "false"
    return {c: out[c] for c in COLUMNS}


def write_regions_csv(rows: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(to_csv_row(r))


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(
        description="법정동 코드 파일과 인구감소지역 목록으로 data/regions.csv 를 만든다.",
        epilog=("가정한 형식: 법정동 코드 파일은 탭 구분, 헤더 `법정동코드`,`법정동명`,`폐지여부`, 인코딩 cp949/utf-8. "
                "인구감소지역 CSV 는 `sggCode` 또는 `시도`,`시군구` 컬럼. 실제 파일로는 검증하지 못했다."))
    p.add_argument("--law-code-file", type=Path, required=True, help="법정동 코드 파일(탭 구분 텍스트)")
    p.add_argument("--depop-file", type=Path, help="인구감소지역 CSV (생략하면 prefCandidate 모두 false)")
    p.add_argument("--out", type=Path, default=DATA_DIR / "regions.csv")
    p.add_argument("--merged-sido-code", help="전남광주통합특별시의 시도 코드 2자리 (파일에서 확인)")
    p.add_argument("--old-gwangju-codes", default="", help="옛 광주 5개 구의 새 시군구 코드, 콤마 구분")
    args = p.parse_args(argv)

    def warn(msg: str) -> None:
        print(f"주의: {msg}", file=sys.stderr)

    try:
        for f in (args.law_code_file, args.depop_file):
            if f and not f.is_file():
                raise FormatError(f"파일이 없습니다: {f}")
        if args.merged_sido_code and not re.fullmatch(r"\d{2}", args.merged_sido_code):
            raise FormatError("--merged-sido-code 는 숫자 2자리여야 합니다")
        old = [c.strip() for c in args.old_gwangju_codes.split(",") if c.strip()]
        if any(not re.fullmatch(r"\d{5}", c) for c in old):
            raise FormatError("--old-gwangju-codes 는 숫자 5자리 코드의 콤마 목록이어야 합니다")
        law = parse_law_rows(read_text_any(args.law_code_file))
        depop = parse_depop(read_text_any(args.depop_file)) if args.depop_file else None
        if depop is None:
            warn("--depop-file 이 없어 prefCandidate 가 모두 false 입니다")
        rows = build_region_rows(law, depop, args.merged_sido_code, old, warn)
    except FormatError as e:
        print(f"입력 형식 오류: {e}", file=sys.stderr)
        return 2
    write_regions_csv(rows, args.out)
    n_city = sum(1 for r in rows if r["memberCodes"])
    print(f"저장: {args.out} ({len(rows)}행, 일반구 합산 시 {n_city}곳, "
          f"prefCandidate {sum(r['prefCandidate'] for r in rows)}곳, 분류 미확정 {sum(r['classUncertain'] for r in rows)}곳)")
    print("주의: 이 표는 [가정] 분류다. 세종·옛 광주 분류와 인구감소지역은 원문으로 확인하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
