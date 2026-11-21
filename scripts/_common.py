"""수집·통계·지역표 스크립트 공통 도구 (표준 라이브러리만 사용).

- 저장소 경로, 인증키 읽기·인코딩·가리기, 계약월(YYYYMM) 계산을 모은다.
- 인증키는 로그·예외·파일에 남기지 않는다. 출력 전에 redact() 를 거친다.
"""
from __future__ import annotations

import os
import re
from fractions import Fraction
from pathlib import Path
from typing import Mapping, Optional
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
KEY_ENV = "DATA_GO_KR_KEY"

# 유형 표기(docs/api-spec.md 와 맞춘 제안값) 순서
HOUSING_TYPES = ("officetel", "detached_multi", "row_multi")


# ---------- 인증키 ----------

def load_env_file(path: Path) -> dict:
    """`KEY=VALUE` 줄만 간단히 읽는다. 주석(#), `export `, 따옴표를 처리한다."""
    out: dict = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, _, value = line.partition("=")
        value = value.strip()
        if value[:1] in ("'", '"') and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        out[name.strip()] = value
    return out


def get_service_key(env: Optional[Mapping[str, str]] = None, env_path: Optional[Path] = None) -> Optional[str]:
    """환경변수 DATA_GO_KR_KEY, 없으면 저장소 루트 .env. 비어 있으면 None."""
    env = os.environ if env is None else env
    value = (env.get(KEY_ENV) or "").strip()
    if not value:
        value = (load_env_file(env_path or ROOT / ".env").get(KEY_ENV) or "").strip()
    return value or None


def normalize_service_key(key: str) -> str:
    """URL 에 붙일 키를 만든다.

    공공데이터포털은 '인코딩된 키'(Encoding, %2B %3D 등이 들어 있음)와 '디코딩된 키'(Decoding,
    +, /, = 가 그대로 있음)를 둘 다 보여 준다. URL 에 직접 이어 붙이므로
    - '%' 가 들어 있으면 이미 인코딩된 키로 보고 그대로 쓴다.
    - 아니면 디코딩된 키로 보고 quote(safe="") 로 인코딩한다(+, /, = 도 변환).
    httpx 의 params= 로 넘기면 이미 인코딩된 키가 한 번 더 인코딩되므로, 완성된 URL 문자열을 쓴다.
    """
    key = key.strip()
    if "%" in key:
        return key
    return quote(key, safe="")


_KEY_PARAM = re.compile(r"(serviceKey=)[^&\s'\"<>]*", re.IGNORECASE)


def redact(text: object, key: Optional[str] = None) -> str:
    """로그·예외 문구에서 인증키를 지운다. serviceKey=값 과 키 원문(인코딩 전후)을 모두 가린다."""
    s = _KEY_PARAM.sub(r"\1***", str(text))
    if key:
        variants = {key, quote(key, safe=""), unquote(key), normalize_service_key(key)}
        for v in sorted(variants, key=len, reverse=True):
            if len(v) >= 4:
                s = s.replace(v, "***")
    return s


# ---------- 계약월 ----------

def parse_ym(text: str) -> tuple:
    """'2026-10' 또는 '202610' -> (2026, 10)."""
    t = text.strip().replace("-", "")
    if not re.fullmatch(r"\d{6}", t):
        raise ValueError(f"계약월 형식이 아닙니다: {text!r} (예: 2026-10)")
    y, m = int(t[:4]), int(t[4:])
    if not 1 <= m <= 12:
        raise ValueError(f"월이 올바르지 않습니다: {text!r}")
    return y, m


def ym_str(y: int, m: int) -> str:
    return f"{y:04d}{m:02d}"


def ym_dash(ym: str) -> str:
    return f"{ym[:4]}-{ym[4:6]}"


def shift_ym(y: int, m: int, delta: int) -> tuple:
    idx = y * 12 + (m - 1) + delta
    return idx // 12, idx % 12 + 1


def month_range(spec: str) -> list:
    """'2025-11:2026-10' 범위, 'a,b,c' 목록, 단일 월을 'YYYYMM' 문자열 목록(오름차순)으로."""
    months: list = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            a, b = part.split(":", 1)
            (y1, m1), (y2, m2) = parse_ym(a), parse_ym(b)
            if (y1, m1) > (y2, m2):
                raise ValueError(f"범위의 시작이 끝보다 늦습니다: {part!r}")
            y, m = y1, m1
            while (y, m) <= (y2, m2):
                months.append(ym_str(y, m))
                y, m = shift_ym(y, m, 1)
        else:
            months.append(ym_str(*parse_ym(part)))
    return sorted(set(months))


def months_before(as_of: str, n: int) -> list:
    """as_of 달은 빼고 직전 n개월('YYYYMM', 오름차순). as_of='2026-11', n=6 -> 202605..202610."""
    y, m = parse_ym(as_of)
    return [ym_str(*shift_ym(y, m, -k)) for k in range(n, 0, -1)]


def to_fraction(value) -> Fraction:
    """float 오차를 피해 문자열 경유로 분수로 바꾼다(0.06 -> 3/50)."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    return Fraction(str(value))


def round_half_up(x: Fraction) -> int:
    """분수를 반올림(.5 는 올림)한 정수."""
    return (x + Fraction(1, 2)).__floor__()
