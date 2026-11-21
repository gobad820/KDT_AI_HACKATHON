"""월세 스냅샷 조회. 형식과 규칙은 docs/data-spec.md 5, 6장.

data/rent_stats.json 이 있으면 그것을, 없으면 설명용 샘플(data/rent_stats.sample.json)을 읽는다.
런타임에 실거래가 API 를 부르지 않는다. 범위를 넓히는 판단은 이 모듈이 하지 않는다.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app import config
from app.schemas import MIN_SAMPLE_COUNT, Rent

from .regions import sido_code_of


def _path() -> Path:
    real = config.DATA_DIR / "rent_stats.json"
    return real if real.exists() else config.DATA_DIR / "rent_stats.sample.json"


@lru_cache(maxsize=1)
def _snapshot() -> dict:
    path = _path()
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_isSample"] = path.name.endswith(".sample.json") or str(data.get("version", "")).startswith("sample")
    return data


def reload() -> None:
    _snapshot.cache_clear()


def snapshot_info() -> dict:
    s = _snapshot()
    return {"version": str(s.get("version", "unknown")), "dataAsOf": str(s.get("dataAsOf", "unknown")),
            "isSample": bool(s["_isSample"])}


def get_rent_stats(sgg_code: str, scope: str = "sgg") -> Optional[Rent]:
    s = _snapshot()
    code = str(sgg_code).strip()
    if scope in ("sgg", "sgg_12m"):
        entry = s.get("stats", {}).get(code, {}).get(scope)
    elif scope == "sido":
        entry = s.get("sidoStats", {}).get(sido_code_of(code))
    else:
        raise ValueError(f"알 수 없는 범위: {scope}")
    if not entry or int(entry.get("sampleCount", 0)) <= 0:
        return None
    counts = entry.get("countsByType") or {}
    types = [t for t, n in counts.items() if n] or list(s.get("housingTypes", []))
    n = int(entry["sampleCount"])
    return Rent(monthly_median=int(entry["monthlyMedian"]), p25=int(entry["p25"]), p75=int(entry["p75"]),
                sample_count=n, period=str(entry["period"]), housing_types=types, scope=scope,
                deposit_basis=int(s.get("depositBasis", 10_000_000)), conversion_rate=float(s.get("conversionRate", 0.06)),
                data_as_of=str(s.get("dataAsOf", "unknown")), sufficient=n >= MIN_SAMPLE_COUNT)
